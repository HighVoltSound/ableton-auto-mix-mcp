use baseview::{WindowHandle, WindowOpenOptions, WindowScalePolicy};
use crossbeam::atomic::AtomicCell;
use nih_plug::prelude::*;
use raw_window_handle::{HasRawWindowHandle, RawWindowHandle};
use serde::{Deserialize, Serialize};
use std::{
    num::NonZeroIsize,
    ptr::NonNull,
    sync::{
        atomic::{AtomicBool, AtomicU32, Ordering},
        Arc,
    },
};

use crate::gui_state::{Genre, GuiState, SourceType, DepthZone, OutputMode};
use crate::StereoEblet3DParams;
use keyboard_types::{Code, KeyState};

mod camera;
mod dome;
mod egui_ui;

pub use camera::Camera;
pub use dome::DomeRenderer;

pub struct WgpuEditorWindow {
    gui_context: Arc<dyn GuiContext>,

    device: wgpu::Device,
    queue: wgpu::Queue,
    surface: wgpu::Surface<'static>,
    surface_config: wgpu::SurfaceConfiguration,

    depth_view: wgpu::TextureView,

    dome_renderer: DomeRenderer,
    camera: Camera,
    gui_state: GuiState,
    params: Arc<StereoEblet3DParams>,
    editor_state: Arc<WgpuEditorState>,

    _last_mouse_pos: Option<(f64, f64)>,
    _is_dragging: bool,

    egui_ctx: egui::Context,
    egui_renderer: egui_wgpu::Renderer,
    scene_texture: wgpu::Texture,
    scene_view: wgpu::TextureView,
    egui_texture_id: Option<egui::TextureId>,
}

impl WgpuEditorWindow {
    fn new(
        window: &mut baseview::Window<'_>,
        gui_context: Arc<dyn GuiContext>,
        params: Arc<StereoEblet3DParams>,
        editor_state: Arc<WgpuEditorState>,
        scaling_factor: f32,
    ) -> Self {
        let target = baseview_window_to_surface_target(window);

        pollster::block_on(Self::create(target, gui_context, params, editor_state, scaling_factor))
    }

    fn handle_keyboard(&mut self, event: &baseview::Event) -> bool {
        match event {
            baseview::Event::Keyboard(kb_event) => {
                if kb_event.state != KeyState::Down {
                    return false;
                }
                match kb_event.code {
                    Code::ArrowLeft => {
                        let new_idx = (self.gui_state.params.genre.index() + Genre::ALL.len() - 1) % Genre::ALL.len();
                        self.gui_state.params.genre = Genre::from_index(new_idx);
                        self.gui_state.params.apply_genre_source(self.gui_state.params.genre, self.gui_state.params.source_type);
                        self.gui_state.params.apply_split_spatial_for_genre();
                        self.sync_params_to_gui();
                        true
                    }
                    Code::ArrowRight => {
                        let new_idx = (self.gui_state.params.genre.index() + 1) % Genre::ALL.len();
                        self.gui_state.params.genre = Genre::from_index(new_idx);
                        self.gui_state.params.apply_genre_source(self.gui_state.params.genre, self.gui_state.params.source_type);
                        self.gui_state.params.apply_split_spatial_for_genre();
                        self.sync_params_to_gui();
                        true
                    }
                    Code::ArrowUp => {
                        let new_idx = (self.gui_state.params.source_type.index() + 1) % SourceType::ALL.len();
                        self.gui_state.params.source_type = SourceType::from_index(new_idx);
                        self.gui_state.params.apply_genre_source(self.gui_state.params.genre, self.gui_state.params.source_type);
                        self.sync_params_to_gui();
                        true
                    }
                    Code::ArrowDown => {
                        let new_idx = (self.gui_state.params.source_type.index() + SourceType::ALL.len() - 1) % SourceType::ALL.len();
                        self.gui_state.params.source_type = SourceType::from_index(new_idx);
                        self.gui_state.params.apply_genre_source(self.gui_state.params.genre, self.gui_state.params.source_type);
                        self.sync_params_to_gui();
                        true
                    }
                    Code::Digit1 => {
                        self.gui_state.params.depth_zone = DepthZone::Front;
                        self.gui_state.params.apply_depth_zone(DepthZone::Front);
                        self.sync_params_to_gui();
                        true
                    }
                    Code::Digit2 => {
                        self.gui_state.params.depth_zone = DepthZone::Mid;
                        self.gui_state.params.apply_depth_zone(DepthZone::Mid);
                        self.sync_params_to_gui();
                        true
                    }
                    Code::Digit3 => {
                        self.gui_state.params.depth_zone = DepthZone::Back;
                        self.gui_state.params.apply_depth_zone(DepthZone::Back);
                        self.sync_params_to_gui();
                        true
                    }
                    Code::Tab => {
                        self.gui_state.params.split_spatial = !self.gui_state.params.split_spatial;
                        if self.gui_state.params.split_spatial {
                            self.gui_state.params.apply_split_spatial_for_genre();
                        }
                        self.sync_params_to_gui();
                        true
                    }
                    Code::KeyH => {
                        self.gui_state.params.output_mode = OutputMode::Headphones;
                        self.sync_params_to_gui();
                        true
                    }
                    Code::KeyC => {
                        self.gui_state.params.output_mode = OutputMode::Club;
                        self.sync_params_to_gui();
                        true
                    }
                    Code::KeyY => {
                        self.gui_state.params.output_mode = OutputMode::Hybrid;
                        self.sync_params_to_gui();
                        true
                    }
                    Code::KeyE => {
                        self.gui_state.params.externalization = (self.gui_state.params.externalization + 0.1).min(1.0);
                        self.sync_params_to_gui();
                        true
                    }
                    Code::KeyQ => {
                        self.gui_state.params.externalization = (self.gui_state.params.externalization - 0.1).max(0.0);
                        self.sync_params_to_gui();
                        true
                    }
                    _ => false,
                }
            }
            _ => false,
        }
    }

    async fn create(
        target: wgpu::SurfaceTargetUnsafe,
        gui_context: Arc<dyn GuiContext>,
        params: Arc<StereoEblet3DParams>,
        editor_state: Arc<WgpuEditorState>,
        scaling_factor: f32,
    ) -> Self {
        let width = (900.0 * scaling_factor as f64).round() as u32;
        let height = (600.0 * scaling_factor as f64).round() as u32;

        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor::default());

        let surface = unsafe { instance.create_surface_unsafe(target) }.unwrap();

        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::LowPower,
                force_fallback_adapter: false,
                compatible_surface: Some(&surface),
            })
            .await
            .expect("Failed to find an appropriate adapter");

        let (device, queue) = adapter
            .request_device(&wgpu::DeviceDescriptor {
                label: Some("Stereo Eblet 3D"),
                required_features: wgpu::Features::empty(),
                required_limits: wgpu::Limits::downlevel_webgl2_defaults()
                    .using_resolution(adapter.limits()),
                memory_hints: wgpu::MemoryHints::MemoryUsage,
            }, None)
            .await
            .expect("Failed to create device");

        let swapchain_capabilities = surface.get_capabilities(&adapter);
        let swapchain_format = swapchain_capabilities.formats[0];

        let surface_config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format: swapchain_format,
            width,
            height,
            present_mode: wgpu::PresentMode::AutoVsync,
            alpha_mode: swapchain_capabilities.alpha_modes[0],
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &surface_config);

        let depth_texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Depth Texture"),
            size: wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Depth32Float,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });
        let depth_view = depth_texture.create_view(&wgpu::TextureViewDescriptor::default());

        let dome_renderer = DomeRenderer::new(&device, swapchain_format);
        let camera = Camera::new();

        let scene_texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Scene Texture"),
            size: wgpu::Extent3d { width, height, depth_or_array_layers: 1 },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING,
            view_formats: &[],
        });
        let scene_view = scene_texture.create_view(&wgpu::TextureViewDescriptor::default());

        let egui_ctx = egui::Context::default();
        let egui_renderer = egui_wgpu::Renderer::new(
            &device,
            swapchain_format,
            Some(wgpu::TextureFormat::Depth32Float),
            1,
            false,
        );

        Self {
            gui_context,
            device,
            queue,
            surface,
            surface_config,
            depth_view,
            dome_renderer,
            camera,
            gui_state: GuiState::new(),
            params,
            editor_state,
            _last_mouse_pos: None,
            _is_dragging: false,
            egui_ctx,
            egui_renderer,
            scene_texture,
            scene_view,
            egui_texture_id: None,
        }
    }

    fn create_depth_texture(&mut self) {
        let texture = self.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Depth Texture"),
            size: wgpu::Extent3d {
                width: self.surface_config.width,
                height: self.surface_config.height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Depth32Float,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });
        self.depth_view = texture.create_view(&wgpu::TextureViewDescriptor::default());

        self.scene_texture = self.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("Scene Texture"),
            size: wgpu::Extent3d {
                width: self.surface_config.width,
                height: self.surface_config.height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8UnormSrgb,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::TEXTURE_BINDING,
            view_formats: &[],
        });
        self.scene_view = self.scene_texture.create_view(&wgpu::TextureViewDescriptor::default());
        self.egui_texture_id = None;
    }

    fn sync_params_to_gui(&mut self) {
        let setter = ParamSetter::new(self.gui_context.as_ref());
        let azimuth = self.gui_state.params.position.azimuth;
        let elevation = self.gui_state.params.position.elevation;
        let distance = self.gui_state.params.position.distance;
        let head_traj = self.gui_state.params.position.head_trajectory();

        setter.set_parameter(&self.params.azimuth, azimuth);
        setter.set_parameter(&self.params.elevation, elevation);
        setter.set_parameter(&self.params.distance, distance);
        setter.set_parameter(&self.params.head_position, head_traj);
        setter.set_parameter(&self.params.bass_mono, self.gui_state.params.bass_mono);
        setter.set_parameter(&self.params.room_model, self.gui_state.params.room as i32);
        setter.set_parameter(&self.params.room_amount, self.gui_state.params.room_amount);
        setter.set_parameter(&self.params.mix, self.gui_state.params.mix);

        setter.set_parameter(&self.params.genre, self.gui_state.params.genre as i32);
        setter.set_parameter(&self.params.source_type, self.gui_state.params.source_type as i32);
        setter.set_parameter(&self.params.depth_zone, self.gui_state.params.depth_zone as i32);
        setter.set_parameter(&self.params.output_mode, self.gui_state.params.output_mode as i32);
        setter.set_parameter(&self.params.split_spatial, self.gui_state.params.split_spatial);
        setter.set_parameter(&self.params.sub_width, self.gui_state.params.sub_width);
        setter.set_parameter(&self.params.low_width, self.gui_state.params.low_width);
        setter.set_parameter(&self.params.mid_width, self.gui_state.params.mid_width);
        setter.set_parameter(&self.params.high_width, self.gui_state.params.high_width);
        setter.set_parameter(&self.params.externalization, self.gui_state.params.externalization);
    }
}

impl baseview::WindowHandler for WgpuEditorWindow {
    fn on_frame(&mut self, _window: &mut baseview::Window) {
        let frame = self
            .surface
            .get_current_texture()
            .expect("Failed to acquire next swap chain texture");
        let view = frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("Stereo Eblet 3D Encoder"),
            });

        let aspect = self.surface_config.width as f32 / self.surface_config.height as f32;
        let view_proj = self.camera.view_projection_matrix(aspect);

        self.dome_renderer.update_uniforms(
            &self.queue,
            &view_proj,
            &self.gui_state.params.position,
            &self.camera,
            0.0,
        );

        {
            let scene_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("Scene Pass"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &self.scene_view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.04,
                            g: 0.04,
                            b: 0.1,
                            a: 1.0,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                    view: &self.depth_view,
                    depth_ops: Some(wgpu::Operations {
                        load: wgpu::LoadOp::Clear(1.0),
                        store: wgpu::StoreOp::Store,
                    }),
                    stencil_ops: None,
                }),
                timestamp_writes: None,
                occlusion_query_set: None,
            });

            let mut scene_pass = scene_pass.forget_lifetime();
            self.dome_renderer.render(&mut scene_pass);
        }

        if self.egui_texture_id.is_none() {
            self.egui_texture_id = Some(self.egui_renderer.register_native_texture(
                &self.device,
                &self.scene_view,
                wgpu::FilterMode::Linear,
            ));
        }

        let raw_input = egui::RawInput {
            screen_rect: Some(egui::Rect::from_min_size(
                egui::Pos2::ZERO,
                egui::Vec2::new(self.surface_config.width as f32, self.surface_config.height as f32),
            )),
            ..Default::default()
        };
        let tex_id = self.egui_texture_id.unwrap();
        let screen_size = egui::Vec2::new(self.surface_config.width as f32, self.surface_config.height as f32);
        let full_output = self.egui_ctx.run(raw_input, |ctx| {
            egui_ui::draw_ui(ctx, &mut self.gui_state, tex_id, screen_size, Some(&self.editor_state));
        });

        for (id, delta) in &full_output.textures_delta.set {
            self.egui_renderer.update_texture(&self.device, &self.queue, *id, delta);
        }

        let screen_descriptor = egui_wgpu::ScreenDescriptor {
            size_in_pixels: [self.surface_config.width, self.surface_config.height],
            pixels_per_point: 1.0,
        };

        let paint_jobs = self.egui_ctx.tessellate(full_output.shapes, 1.0);

        let user_cmd_bufs = self.egui_renderer.update_buffers(
            &self.device,
            &self.queue,
            &mut encoder,
            &paint_jobs,
            &screen_descriptor,
        );

        {
            let egui_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("Egui Pass"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.04,
                            g: 0.04,
                            b: 0.1,
                            a: 1.0,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });

            let mut egui_pass = egui_pass.forget_lifetime();
            self.egui_renderer.render(&mut egui_pass, &paint_jobs, &screen_descriptor);
        }

        for cmd in user_cmd_bufs {
            self.queue.submit(std::iter::once(cmd));
        }
        self.queue.submit(Some(encoder.finish()));

        for id in &full_output.textures_delta.free {
            self.egui_renderer.free_texture(id);
        }

        frame.present();
    }

    fn on_event(
        &mut self,
        _window: &mut baseview::Window,
        event: baseview::Event,
    ) -> baseview::EventStatus {
        // Handle keyboard first
        if self.handle_keyboard(&event) {
            return baseview::EventStatus::Captured;
        }

        match &event {
            baseview::Event::Window(baseview::WindowEvent::Resized(window_info)) => {
                let logical = window_info.logical_size();
                let physical = window_info.physical_size();

                self.surface_config.width = physical.width;
                self.surface_config.height = physical.height;
                self.surface.configure(&self.device, &self.surface_config);
                self.create_depth_texture();

                let _ = logical;
            }
            baseview::Event::Mouse(mouse_event) => match mouse_event {
                baseview::MouseEvent::ButtonPressed { .. } => {
                    self._is_dragging = true;
                }
                baseview::MouseEvent::CursorMoved { position, .. } => {
                    let x = position.x;
                    let y = position.y;

                    if self._is_dragging {
                        if let Some((last_x, last_y)) = self._last_mouse_pos {
                            let dx = x - last_x;
                            let dy = y - last_y;

                            self.gui_state.params.position.azimuth += dx as f32 * 0.5;
                            self.gui_state.params.position.elevation += dy as f32 * 0.5;

                            self.gui_state.params.position.azimuth =
                                self.gui_state.params.position.azimuth.clamp(-180.0, 180.0);
                            self.gui_state.params.position.elevation =
                                self.gui_state.params.position.elevation.clamp(-90.0, 90.0);

                            self.sync_params_to_gui();
                        }
                        self._last_mouse_pos = Some((x, y));
                    } else {
                        self._last_mouse_pos = Some((x, y));
                    }
                }
                baseview::MouseEvent::ButtonReleased { .. } => {
                    self._is_dragging = false;
                    self._last_mouse_pos = None;
                }
                _ => {}
            },
            _ => {}
        }

        baseview::EventStatus::Captured
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct WgpuEditorState {
    #[serde(with = "nih_plug::params::persist::serialize_atomic_cell")]
    size: AtomicCell<(u32, u32)>,
    #[serde(skip)]
    open: AtomicBool,
    #[serde(skip)]
    cpu_usage: Arc<AtomicU32>,
}

impl WgpuEditorState {
    pub fn from_size(size: (u32, u32)) -> Arc<Self> {
        Arc::new(Self {
            size: AtomicCell::new(size),
            open: AtomicBool::new(false),
            cpu_usage: Arc::new(AtomicU32::new(0)),
        })
    }

    pub fn size(&self) -> (u32, u32) {
        self.size.load()
    }

    pub fn is_open(&self) -> bool {
        self.open.load(Ordering::Acquire)
    }

    pub fn cpu_usage(&self) -> &Arc<AtomicU32> {
        &self.cpu_usage
    }

    pub fn set_cpu_usage(&self, usage: f32) {
        self.cpu_usage.store((usage * 100.0) as u32, Ordering::Relaxed);
    }
}

impl<'a> nih_plug::params::persist::PersistentField<'a, WgpuEditorState> for Arc<WgpuEditorState> {
    fn set(&self, new_value: WgpuEditorState) {
        self.size.store(new_value.size.load());
    }

    fn map<F, R>(&self, f: F) -> R
    where
        F: Fn(&WgpuEditorState) -> R,
    {
        f(self)
    }
}

pub struct WgpuEditor {
    params: Arc<StereoEblet3DParams>,
    editor_state: Arc<WgpuEditorState>,
    scaling_factor: AtomicCell<Option<f32>>,
}

impl WgpuEditor {
    pub fn new(params: Arc<StereoEblet3DParams>, editor_state: Arc<WgpuEditorState>) -> Self {
        Self {
            params,
            editor_state,
            scaling_factor: AtomicCell::new(Some(1.0)),
        }
    }
}

impl Editor for WgpuEditor {
    fn spawn(
        &self,
        parent: ParentWindowHandle,
        context: Arc<dyn GuiContext>,
    ) -> Box<dyn std::any::Any + Send> {
        let (unscaled_width, unscaled_height) = self.editor_state.size();
        let scaling_factor = self.scaling_factor.load();

        let gui_context = Arc::clone(&context);
        let params = Arc::clone(&self.params);
        let editor_state = Arc::clone(&self.editor_state);

        let window = baseview::Window::open_parented(
            &ParentWindowHandleAdapter(parent),
            WindowOpenOptions {
                title: String::from("Stereo Eblet 3D"),
                size: baseview::Size::new(unscaled_width as f64, unscaled_height as f64),
                scale: scaling_factor
                    .map(|factor| WindowScalePolicy::ScaleFactor(factor as f64))
                    .unwrap_or(WindowScalePolicy::SystemScaleFactor),
                gl_config: None,
            },
            move |window: &mut baseview::Window<'_>| -> WgpuEditorWindow {
                WgpuEditorWindow::new(
                    window,
                    gui_context,
                    params,
                    editor_state,
                    scaling_factor.unwrap_or(1.0),
                )
            },
        );

        self.editor_state.open.store(true, Ordering::Release);
        Box::new(WgpuEditorHandle {
            state: self.editor_state.clone(),
            window,
        })
    }

    fn size(&self) -> (u32, u32) {
        self.editor_state.size()
    }

    fn set_scale_factor(&self, factor: f32) -> bool {
        if self.editor_state.is_open() {
            return false;
        }
        self.scaling_factor.store(Some(factor));
        true
    }

    fn param_value_changed(&self, _id: &str, _normalized_value: f32) {}
    fn param_modulation_changed(&self, _id: &str, _modulation_offset: f32) {}
    fn param_values_changed(&self) {}
}

struct WgpuEditorHandle {
    state: Arc<WgpuEditorState>,
    window: WindowHandle,
}

unsafe impl Send for WgpuEditorHandle {}

impl Drop for WgpuEditorHandle {
    fn drop(&mut self) {
        self.state.open.store(false, Ordering::Release);
        self.window.close();
    }
}

struct ParentWindowHandleAdapter(nih_plug::editor::ParentWindowHandle);

unsafe impl HasRawWindowHandle for ParentWindowHandleAdapter {
    fn raw_window_handle(&self) -> RawWindowHandle {
        match self.0 {
            ParentWindowHandle::X11Window(window) => {
                let mut handle = raw_window_handle::XcbWindowHandle::empty();
                handle.window = window;
                RawWindowHandle::Xcb(handle)
            }
            ParentWindowHandle::AppKitNsView(ns_view) => {
                let mut handle = raw_window_handle::AppKitWindowHandle::empty();
                handle.ns_view = ns_view;
                RawWindowHandle::AppKit(handle)
            }
            ParentWindowHandle::Win32Hwnd(hwnd) => {
                let mut handle = raw_window_handle::Win32WindowHandle::empty();
                handle.hwnd = hwnd;
                RawWindowHandle::Win32(handle)
            }
        }
    }
}

fn baseview_window_to_surface_target(window: &baseview::Window<'_>) -> wgpu::SurfaceTargetUnsafe {
    use raw_window_handle::{HasRawDisplayHandle, HasRawWindowHandle};

    let raw_display_handle = window.raw_display_handle();
    let raw_window_handle = window.raw_window_handle();

    wgpu::SurfaceTargetUnsafe::RawHandle {
        raw_display_handle: match raw_display_handle {
            raw_window_handle::RawDisplayHandle::AppKit(_) => {
                raw_window_handle_06::RawDisplayHandle::AppKit(
                    raw_window_handle_06::AppKitDisplayHandle::new(),
                )
            }
            raw_window_handle::RawDisplayHandle::Xlib(handle) => {
                raw_window_handle_06::RawDisplayHandle::Xlib(
                    raw_window_handle_06::XlibDisplayHandle::new(
                        NonNull::new(handle.display),
                        handle.screen,
                    ),
                )
            }
            raw_window_handle::RawDisplayHandle::Xcb(handle) => {
                raw_window_handle_06::RawDisplayHandle::Xcb(
                    raw_window_handle_06::XcbDisplayHandle::new(
                        NonNull::new(handle.connection),
                        handle.screen,
                    ),
                )
            }
            raw_window_handle::RawDisplayHandle::Windows(_) => {
                raw_window_handle_06::RawDisplayHandle::Windows(
                    raw_window_handle_06::WindowsDisplayHandle::new(),
                )
            }
            _ => todo!("Unsupported display handle"),
        },
        raw_window_handle: match raw_window_handle {
            raw_window_handle::RawWindowHandle::AppKit(handle) => {
                raw_window_handle_06::RawWindowHandle::AppKit(
                    raw_window_handle_06::AppKitWindowHandle::new(
                        NonNull::new(handle.ns_view).unwrap(),
                    ),
                )
            }
            raw_window_handle::RawWindowHandle::Xlib(handle) => {
                raw_window_handle_06::RawWindowHandle::Xlib(
                    raw_window_handle_06::XlibWindowHandle::new(handle.window),
                )
            }
            raw_window_handle::RawWindowHandle::Xcb(handle) => {
                raw_window_handle_06::RawWindowHandle::Xcb(
                    raw_window_handle_06::XcbWindowHandle::new(
                        std::num::NonZeroU32::new(handle.window).unwrap(),
                    ),
                )
            }
            raw_window_handle::RawWindowHandle::Win32(handle) => {
                let mut raw_handle = raw_window_handle_06::Win32WindowHandle::new(
                    NonZeroIsize::new(handle.hwnd as isize).unwrap(),
                );
                raw_handle.hinstance = NonZeroIsize::new(handle.hinstance as isize);
                raw_window_handle_06::RawWindowHandle::Win32(raw_handle)
            }
            _ => todo!("Unsupported window handle"),
        },
    }
}
