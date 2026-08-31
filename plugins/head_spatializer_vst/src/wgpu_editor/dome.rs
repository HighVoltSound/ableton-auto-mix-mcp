use crate::gui_state::OrbPosition;
use crate::wgpu_editor::camera::Camera;
use std::borrow::Cow;
use std::f32::consts::PI;
use wgpu::util::DeviceExt;

const DOME_SHADER: &str = r#"
struct Uniforms {
    view_proj: mat4x4<f32>,
    time: f32,
    azimuth: f32,
    elevation: f32,
    distance: f32,
    camera_pos: vec3<f32>,
};

@group(0) @binding(0)
var<uniform> uniforms: Uniforms;

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) world_pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) uv: vec2<f32>,
};

@vertex
fn vs_main(
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) uv: vec2<f32>,
) -> VertexOutput {
    var out: VertexOutput;
    out.clip_position = uniforms.view_proj * vec4<f32>(position, 1.0);
    out.world_pos = position;
    out.normal = normal;
    out.uv = uv;
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let view_dir = normalize(uniforms.camera_pos - in.world_pos);
    let fresnel = pow(1.0 - max(dot(view_dir, in.normal), 0.0), 3.0);

    let teal = vec3<f32>(0.059, 0.941, 0.988);
    let base_color = mix(vec3<f32>(0.02, 0.02, 0.05), teal, fresnel * 0.6);

    let alpha = mix(0.05, 0.4, fresnel);

    return vec4<f32>(base_color, alpha);
}
"#;

const ORB_SHADER: &str = r#"
struct Uniforms {
    view_proj: mat4x4<f32>,
    time: f32,
    azimuth: f32,
    elevation: f32,
    distance: f32,
    camera_pos: vec3<f32>,
};

@group(0) @binding(0)
var<uniform> uniforms: Uniforms;

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) world_pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
};

@vertex
fn vs_main(
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
) -> VertexOutput {
    var out: VertexOutput;
    out.clip_position = uniforms.view_proj * vec4<f32>(position, 1.0);
    out.world_pos = position;
    out.normal = normal;
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let view_dir = normalize(uniforms.camera_pos - in.world_pos);
    let fresnel = pow(1.0 - max(dot(view_dir, in.normal), 0.0), 2.0);

    let coral = vec3<f32>(1.0, 0.42, 0.21);
    let glow = vec3<f32>(1.0, 0.6, 0.4);

    let color = mix(coral, glow, fresnel);
    let pulse = 0.8 + 0.2 * sin(uniforms.time * 3.0);

    return vec4<f32>(color * pulse, 1.0);
}
"#;

const HEAD_SHADER: &str = r#"
struct Uniforms {
    view_proj: mat4x4<f32>,
    time: f32,
    azimuth: f32,
    elevation: f32,
    distance: f32,
    camera_pos: vec3<f32>,
};

@group(0) @binding(0)
var<uniform> uniforms: Uniforms;

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) world_pos: vec3<f32>,
    @location(1) normal: vec3<f32>,
};

@vertex
fn vs_main(
    @location(0) position: vec3<f32>,
    @location(1) normal: vec3<f32>,
    @location(2) uv: vec2<f32>,
) -> VertexOutput {
    var out: VertexOutput;
    out.clip_position = uniforms.view_proj * vec4<f32>(position, 1.0);
    out.world_pos = position;
    out.normal = normal;
    return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    let view_dir = normalize(uniforms.camera_pos - in.world_pos);
    let fresnel = pow(1.0 - max(dot(view_dir, in.normal), 0.0), 2.5);

    let teal = vec3<f32>(0.059, 0.941, 0.988);
    let dark = vec3<f32>(0.02, 0.08, 0.1);
    let color = mix(dark, teal, 0.6 + fresnel * 0.4);

    return vec4<f32>(color, 1.0);
}
"#;

const LINES_SHADER: &str = r#"
struct Uniforms {
    view_proj: mat4x4<f32>,
};

@group(0) @binding(0) var<uniform> uniforms: Uniforms;

struct VertexInput {
    @location(0) pos: vec3<f32>,
    @location(1) color: vec3<f32>,
};

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) color: vec3<f32>,
};

@vertex fn vs_main(in: VertexInput) -> VertexOutput {
    var out: VertexOutput;
    out.clip_position = uniforms.view_proj * vec4<f32>(in.pos, 1.0);
    out.color = in.color;
    return out;
}

@fragment fn fs_main(in: VertexOutput) -> @location(0) vec4<f32> {
    return vec4<f32>(in.color, 0.6);
}
"#;

pub struct DomeRenderer {
    dome_pipeline: wgpu::RenderPipeline,
    dome_vertex_buffer: wgpu::Buffer,
    dome_index_buffer: wgpu::Buffer,
    dome_index_count: u32,

    orb_pipeline: wgpu::RenderPipeline,
    orb_vertex_buffer: wgpu::Buffer,
    orb_index_buffer: wgpu::Buffer,
    orb_index_count: u32,

    uniform_buffer: wgpu::Buffer,
    uniform_bind_group: wgpu::BindGroup,

    head_renderer: HeadRenderer,
    lines_renderer: LinesRenderer,
}

#[repr(C)]
#[derive(Copy, Clone, bytemuck::Pod, bytemuck::Zeroable)]
struct Uniforms {
    view_proj: [[f32; 4]; 4],
    time: f32,
    azimuth: f32,
    elevation: f32,
    distance: f32,
    camera_pos: [f32; 3],
    _pad: f32,
}

#[repr(C)]
#[derive(Copy, Clone, bytemuck::Pod, bytemuck::Zeroable)]
struct DomeVertex {
    position: [f32; 3],
    normal: [f32; 3],
    uv: [f32; 2],
}

#[repr(C)]
#[derive(Copy, Clone, bytemuck::Pod, bytemuck::Zeroable)]
struct LineVertex {
    position: [f32; 3],
    color: [f32; 3],
}

#[repr(C)]
#[derive(Copy, Clone, bytemuck::Pod, bytemuck::Zeroable)]
struct LinesUniforms {
    view_proj: [[f32; 4]; 4],
}

pub struct HeadRenderer {
    pipeline: wgpu::RenderPipeline,
    vertex_buffer: wgpu::Buffer,
    index_buffer: wgpu::Buffer,
    index_count: u32,
}

impl HeadRenderer {
    pub fn new(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
        uniform_bind_group_layout: &wgpu::BindGroupLayout,
    ) -> Self {
        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Head Shader"),
            source: wgpu::ShaderSource::Wgsl(Cow::Borrowed(HEAD_SHADER)),
        });

        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("Head Pipeline Layout"),
            bind_group_layouts: &[uniform_bind_group_layout],
            push_constant_ranges: &[],
        });

        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("Head Pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_main"),
                buffers: &[wgpu::VertexBufferLayout {
                    array_stride: std::mem::size_of::<DomeVertex>() as u64,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &[
                        wgpu::VertexAttribute {
                            offset: 0,
                            shader_location: 0,
                            format: wgpu::VertexFormat::Float32x3,
                        },
                        wgpu::VertexAttribute {
                            offset: 12,
                            shader_location: 1,
                            format: wgpu::VertexFormat::Float32x3,
                        },
                        wgpu::VertexAttribute {
                            offset: 24,
                            shader_location: 2,
                            format: wgpu::VertexFormat::Float32x2,
                        },
                    ],
                }],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_main"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: None,
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleList,
                cull_mode: Some(wgpu::Face::Back),
                ..Default::default()
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth32Float,
                depth_write_enabled: true,
                depth_compare: wgpu::CompareFunction::Less,
                stencil: wgpu::StencilState::default(),
                bias: wgpu::DepthBiasState::default(),
            }),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

        let (verts, indices) = generate_head_mesh();
        let vertex_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Head VB"),
            contents: bytemuck::cast_slice(&verts),
            usage: wgpu::BufferUsages::VERTEX,
        });
        let index_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Head IB"),
            contents: bytemuck::cast_slice(&indices),
            usage: wgpu::BufferUsages::INDEX,
        });
        let index_count = indices.len() as u32;

        Self {
            pipeline,
            vertex_buffer,
            index_buffer,
            index_count,
        }
    }

    pub fn render(&self, rpass: &mut wgpu::RenderPass<'static>, bind_group: &wgpu::BindGroup) {
        rpass.set_pipeline(&self.pipeline);
        rpass.set_bind_group(0, bind_group, &[]);
        rpass.set_vertex_buffer(0, self.vertex_buffer.slice(..));
        rpass.set_index_buffer(self.index_buffer.slice(..), wgpu::IndexFormat::Uint32);
        rpass.draw_indexed(0..self.index_count, 0, 0..1);
    }
}

pub struct LinesRenderer {
    pipeline: wgpu::RenderPipeline,
    vertex_buffer: wgpu::Buffer,
    vertex_count: u32,
    uniform_buffer: wgpu::Buffer,
    uniform_bind_group: wgpu::BindGroup,
}

impl LinesRenderer {
    pub fn new(device: &wgpu::Device, format: wgpu::TextureFormat) -> Self {
        let uniform_buffer = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("Lines Uniform Buffer"),
            size: std::mem::size_of::<LinesUniforms>() as u64,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let uniform_bind_group_layout =
            device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
                label: Some("Lines Uniform BGL"),
                entries: &[wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX | wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        has_dynamic_offset: false,
                        min_binding_size: Some(
                            std::num::NonZeroU64::new(std::mem::size_of::<LinesUniforms>() as u64)
                                .unwrap(),
                        ),
                        ty: wgpu::BufferBindingType::Uniform,
                    },
                    count: None,
                }],
            });

        let uniform_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("Lines Uniform BG"),
            layout: &uniform_bind_group_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: uniform_buffer.as_entire_binding(),
            }],
        });

        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Lines Shader"),
            source: wgpu::ShaderSource::Wgsl(Cow::Borrowed(LINES_SHADER)),
        });

        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("Lines Pipeline Layout"),
            bind_group_layouts: &[&uniform_bind_group_layout],
            push_constant_ranges: &[],
        });

        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("Lines Pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_main"),
                buffers: &[wgpu::VertexBufferLayout {
                    array_stride: std::mem::size_of::<LineVertex>() as u64,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &[
                        wgpu::VertexAttribute {
                            offset: 0,
                            shader_location: 0,
                            format: wgpu::VertexFormat::Float32x3,
                        },
                        wgpu::VertexAttribute {
                            offset: 12,
                            shader_location: 1,
                            format: wgpu::VertexFormat::Float32x3,
                        },
                    ],
                }],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_main"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::LineList,
                cull_mode: None,
                ..Default::default()
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth32Float,
                depth_write_enabled: false,
                depth_compare: wgpu::CompareFunction::LessEqual,
                stencil: wgpu::StencilState::default(),
                bias: wgpu::DepthBiasState::default(),
            }),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

        let mut vertices = Vec::new();
        vertices.extend(generate_distance_rings());
        vertices.extend(generate_latitude_arcs());
        let vertex_count = vertices.len() as u32;

        let vertex_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Lines VB"),
            contents: bytemuck::cast_slice(&vertices),
            usage: wgpu::BufferUsages::VERTEX,
        });

        Self {
            pipeline,
            vertex_buffer,
            vertex_count,
            uniform_buffer,
            uniform_bind_group,
        }
    }

    pub fn update_uniforms(&self, queue: &wgpu::Queue, view_proj: &[[f32; 4]; 4]) {
        let uniforms = LinesUniforms { view_proj: *view_proj };
        queue.write_buffer(&self.uniform_buffer, 0, bytemuck::bytes_of(&uniforms));
    }

    pub fn render(&self, rpass: &mut wgpu::RenderPass<'static>) {
        if self.vertex_count == 0 {
            return;
        }
        rpass.set_pipeline(&self.pipeline);
        rpass.set_bind_group(0, &self.uniform_bind_group, &[]);
        rpass.set_vertex_buffer(0, self.vertex_buffer.slice(..));
        rpass.draw(0..self.vertex_count, 0..1);
    }
}

impl DomeRenderer {
    pub fn new(device: &wgpu::Device, format: wgpu::TextureFormat) -> Self {
        let uniform_buffer = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("Dome Uniform Buffer"),
            size: std::mem::size_of::<Uniforms>() as u64,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });

        let uniform_bind_group_layout =
            device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
                label: Some("Dome Uniform BGL"),
                entries: &[wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX | wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Buffer {
                        has_dynamic_offset: false,
                        min_binding_size: Some(
                            std::num::NonZeroU64::new(std::mem::size_of::<Uniforms>() as u64)
                                .unwrap(),
                        ),
                        ty: wgpu::BufferBindingType::Uniform,
                    },
                    count: None,
                }],
            });

        let uniform_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("Dome Uniform BG"),
            layout: &uniform_bind_group_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: uniform_buffer.as_entire_binding(),
            }],
        });

        let dome_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Dome Shader"),
            source: wgpu::ShaderSource::Wgsl(Cow::Borrowed(DOME_SHADER)),
        });

        let dome_pipeline_layout =
            device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
                label: Some("Dome Pipeline Layout"),
                bind_group_layouts: &[&uniform_bind_group_layout],
                push_constant_ranges: &[],
            });

        let dome_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("Dome Pipeline"),
            layout: Some(&dome_pipeline_layout),
            vertex: wgpu::VertexState {
                module: &dome_shader,
                entry_point: Some("vs_main"),
                buffers: &[wgpu::VertexBufferLayout {
                    array_stride: std::mem::size_of::<DomeVertex>() as u64,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &[
                        wgpu::VertexAttribute {
                            offset: 0,
                            shader_location: 0,
                            format: wgpu::VertexFormat::Float32x3,
                        },
                        wgpu::VertexAttribute {
                            offset: 12,
                            shader_location: 1,
                            format: wgpu::VertexFormat::Float32x3,
                        },
                        wgpu::VertexAttribute {
                            offset: 24,
                            shader_location: 2,
                            format: wgpu::VertexFormat::Float32x2,
                        },
                    ],
                }],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &dome_shader,
                entry_point: Some("fs_main"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleList,
                cull_mode: None,
                ..Default::default()
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth32Float,
                depth_write_enabled: false,
                depth_compare: wgpu::CompareFunction::LessEqual,
                stencil: wgpu::StencilState::default(),
                bias: wgpu::DepthBiasState::default(),
            }),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

        let (dome_verts, dome_indices) = Self::generate_dome_mesh(1.0, 32, 16);
        let dome_vertex_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Dome VB"),
            contents: bytemuck::cast_slice(&dome_verts),
            usage: wgpu::BufferUsages::VERTEX,
        });
        let dome_index_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Dome IB"),
            contents: bytemuck::cast_slice(&dome_indices),
            usage: wgpu::BufferUsages::INDEX,
        });
        let dome_index_count = dome_indices.len() as u32;

        let orb_shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("Orb Shader"),
            source: wgpu::ShaderSource::Wgsl(Cow::Borrowed(ORB_SHADER)),
        });

        let orb_pipeline_layout =
            device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
                label: Some("Orb Pipeline Layout"),
                bind_group_layouts: &[&uniform_bind_group_layout],
                push_constant_ranges: &[],
            });

        let orb_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("Orb Pipeline"),
            layout: Some(&orb_pipeline_layout),
            vertex: wgpu::VertexState {
                module: &orb_shader,
                entry_point: Some("vs_main"),
                buffers: &[wgpu::VertexBufferLayout {
                    array_stride: (std::mem::size_of::<f32>() * 6) as u64,
                    step_mode: wgpu::VertexStepMode::Vertex,
                    attributes: &[
                        wgpu::VertexAttribute {
                            offset: 0,
                            shader_location: 0,
                            format: wgpu::VertexFormat::Float32x3,
                        },
                        wgpu::VertexAttribute {
                            offset: 12,
                            shader_location: 1,
                            format: wgpu::VertexFormat::Float32x3,
                        },
                    ],
                }],
                compilation_options: Default::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &orb_shader,
                entry_point: Some("fs_main"),
                compilation_options: Default::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleList,
                cull_mode: Some(wgpu::Face::Back),
                ..Default::default()
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth32Float,
                depth_write_enabled: true,
                depth_compare: wgpu::CompareFunction::Less,
                stencil: wgpu::StencilState::default(),
                bias: wgpu::DepthBiasState::default(),
            }),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });

        let (orb_verts, orb_indices) = Self::generate_sphere_mesh(0.08, 16, 12);
        let orb_vertex_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Orb VB"),
            contents: bytemuck::cast_slice(&orb_verts),
            usage: wgpu::BufferUsages::VERTEX,
        });
        let orb_index_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("Orb IB"),
            contents: bytemuck::cast_slice(&orb_indices),
            usage: wgpu::BufferUsages::INDEX,
        });
        let orb_index_count = orb_indices.len() as u32;

        let head_renderer = HeadRenderer::new(device, format, &uniform_bind_group_layout);
        let lines_renderer = LinesRenderer::new(device, format);

        Self {
            dome_pipeline,
            dome_vertex_buffer,
            dome_index_buffer,
            dome_index_count,
            orb_pipeline,
            orb_vertex_buffer,
            orb_index_buffer,
            orb_index_count,
            uniform_buffer,
            uniform_bind_group,
            head_renderer,
            lines_renderer,
        }
    }

    pub fn update_uniforms(
        &self,
        queue: &wgpu::Queue,
        view_proj: &[[f32; 4]; 4],
        position: &OrbPosition,
        camera: &Camera,
        time: f32,
    ) {
        let uniforms = Uniforms {
            view_proj: *view_proj,
            time,
            azimuth: position.azimuth.to_radians(),
            elevation: position.elevation.to_radians(),
            distance: position.distance,
            camera_pos: camera.position(),
            _pad: 0.0,
        };
        queue.write_buffer(&self.uniform_buffer, 0, bytemuck::bytes_of(&uniforms));
        self.lines_renderer.update_uniforms(queue, view_proj);
    }

    pub fn render(
        &self,
        rpass: &mut wgpu::RenderPass<'static>,
    ) {
        self.head_renderer.render(rpass, &self.uniform_bind_group);

        self.lines_renderer.render(rpass);

        rpass.set_pipeline(&self.orb_pipeline);
        rpass.set_bind_group(0, &self.uniform_bind_group, &[]);
        rpass.set_vertex_buffer(0, self.orb_vertex_buffer.slice(..));
        rpass.set_index_buffer(self.orb_index_buffer.slice(..), wgpu::IndexFormat::Uint32);
        rpass.draw_indexed(0..self.orb_index_count, 0, 0..1);

        rpass.set_pipeline(&self.dome_pipeline);
        rpass.set_bind_group(0, &self.uniform_bind_group, &[]);
        rpass.set_vertex_buffer(0, self.dome_vertex_buffer.slice(..));
        rpass.set_index_buffer(self.dome_index_buffer.slice(..), wgpu::IndexFormat::Uint32);
        rpass.draw_indexed(0..self.dome_index_count, 0, 0..1);
    }

    fn generate_dome_mesh(
        radius: f32,
        sectors: u32,
        stacks: u32,
    ) -> (Vec<DomeVertex>, Vec<u32>) {
        let mut vertices = Vec::new();
        let mut indices = Vec::new();

        for stack in 0..=stacks {
            let phi = (stack as f32 / stacks as f32) * PI * 0.5;
            for sector in 0..=sectors {
                let theta = (sector as f32 / sectors as f32) * PI;

                let x = radius * phi.cos() * theta.cos();
                let y = radius * phi.sin();
                let z = radius * phi.cos() * theta.sin();

                let nx = x / radius;
                let ny = y / radius;
                let nz = z / radius;

                let u = sector as f32 / sectors as f32;
                let v = stack as f32 / stacks as f32;

                vertices.push(DomeVertex {
                    position: [x, y, z],
                    normal: [nx, ny, nz],
                    uv: [u, v],
                });
            }
        }

        for stack in 0..stacks {
            for sector in 0..sectors {
                let first = stack * (sectors + 1) + sector;
                let second = first + sectors + 1;

                indices.push(first);
                indices.push(second);
                indices.push(first + 1);

                indices.push(second);
                indices.push(second + 1);
                indices.push(first + 1);
            }
        }

        (vertices, indices)
    }

    fn generate_sphere_mesh(
        radius: f32,
        sectors: u32,
        stacks: u32,
    ) -> (Vec<[f32; 6]>, Vec<u32>) {
        let mut vertices = Vec::new();
        let mut indices = Vec::new();

        for stack in 0..=stacks {
            let phi = (stack as f32 / stacks as f32) * PI;
            for sector in 0..=sectors {
                let theta = (sector as f32 / sectors as f32) * PI * 2.0;

                let x = radius * phi.sin() * theta.cos();
                let y = radius * phi.cos();
                let z = radius * phi.sin() * theta.sin();

                let nx = x / radius;
                let ny = y / radius;
                let nz = z / radius;

                vertices.push([x, y, z, nx, ny, nz]);
            }
        }

        for stack in 0..stacks {
            for sector in 0..sectors {
                let first = stack * (sectors + 1) + sector;
                let second = first + sectors + 1;

                indices.push(first);
                indices.push(second);
                indices.push(first + 1);

                indices.push(second);
                indices.push(second + 1);
                indices.push(first + 1);
            }
        }

        (vertices, indices)
    }
}

fn generate_head_mesh() -> (Vec<DomeVertex>, Vec<u32>) {
    let mut vertices = Vec::new();
    let mut indices = Vec::new();

    // Main skull: ellipsoid 0.15 radius, 1.3x taller (y), 0.9x narrower (x), 1.1x longer (z)
    let rx = 0.15 * 0.9;
    let ry = 0.15 * 1.3;
    let rz = 0.15 * 1.1;
    let sectors = 24u32;
    let stacks = 16u32;

    for stack in 0..=stacks {
        let phi = (stack as f32 / stacks as f32) * PI;
        for sector in 0..=sectors {
            let theta = (sector as f32 / sectors as f32) * PI * 2.0;

            let x = rx * phi.sin() * theta.cos();
            let y = ry * phi.cos();
            let z = rz * phi.sin() * theta.sin();

            let nx = x / (rx * rx);
            let ny = y / (ry * ry);
            let nz = z / (rz * rz);
            let len = (nx * nx + ny * ny + nz * nz).sqrt();
            let (nx, ny, nz) = (nx / len, ny / len, nz / len);

            vertices.push(DomeVertex {
                position: [x, y, z],
                normal: [nx, ny, nz],
                uv: [sector as f32 / sectors as f32, stack as f32 / stacks as f32],
            });
        }
    }

    for stack in 0..stacks {
        for sector in 0..sectors {
            let first = stack * (sectors + 1) + sector;
            let second = first + sectors + 1;

            indices.push(first);
            indices.push(second);
            indices.push(first + 1);

            indices.push(second);
            indices.push(second + 1);
            indices.push(first + 1);
        }
    }

    // Helper: add a half-sphere bump
    let add_bump = |vertices: &mut Vec<DomeVertex>,
                        indices: &mut Vec<u32>,
                        center: [f32; 3],
                        radius: f32,
                        bump_sectors: u32,
                        bump_stacks: u32| {
        let base = vertices.len() as u32;

        for stack in 0..=bump_stacks {
            let phi = (stack as f32 / bump_stacks as f32) * PI * 0.5;
            for sector in 0..=bump_sectors {
                let theta = (sector as f32 / bump_sectors as f32) * PI * 2.0;

                let x = center[0] + radius * phi.sin() * theta.cos();
                let y = center[1] + radius * phi.cos();
                let z = center[2] + radius * phi.sin() * theta.sin();

                let nx = (x - center[0]) / radius;
                let ny = (y - center[1]) / radius;
                let nz = (z - center[2]) / radius;

                vertices.push(DomeVertex {
                    position: [x, y, z],
                    normal: [nx, ny, nz],
                    uv: [sector as f32 / bump_sectors as f32, stack as f32 / bump_stacks as f32],
                });
            }
        }

        for stack in 0..bump_stacks {
            for sector in 0..bump_sectors {
                let first = base + stack * (bump_sectors + 1) + sector;
                let second = first + bump_sectors + 1;

                indices.push(first);
                indices.push(second);
                indices.push(first + 1);

                indices.push(second);
                indices.push(second + 1);
                indices.push(first + 1);
            }
        }
    };

    // Left ear: x=-0.15, y=0.0, z=0.0
    add_bump(
        &mut vertices,
        &mut indices,
        [-0.15, 0.0, 0.0],
        0.04,
        10,
        6,
    );

    // Right ear: x=+0.15, y=0.0, z=0.0
    add_bump(
        &mut vertices,
        &mut indices,
        [0.15, 0.0, 0.0],
        0.04,
        10,
        6,
    );

    // Nose: x=0, y=-0.02, z=0.16
    add_bump(
        &mut vertices,
        &mut indices,
        [0.0, -0.02, 0.16],
        0.03,
        8,
        4,
    );

    (vertices, indices)
}

fn generate_distance_rings() -> Vec<LineVertex> {
    let mut verts = Vec::new();
    let segments = 64u32;
    let color = [0.059, 0.941, 0.988]; // teal
    let distances = [0.5, 1.0, 1.5];

    for &dist in &distances {
        for i in 0..segments {
            let a0 = (i as f32 / segments as f32) * PI * 2.0;
            let a1 = ((i + 1) as f32 / segments as f32) * PI * 2.0;

            verts.push(LineVertex {
                position: [a0.cos() * dist, 0.0, a0.sin() * dist],
                color,
            });
            verts.push(LineVertex {
                position: [a1.cos() * dist, 0.0, a1.sin() * dist],
                color,
            });
        }
    }

    verts
}

fn generate_latitude_arcs() -> Vec<LineVertex> {
    let mut verts = Vec::new();
    let segments = 64u32;
    let color = [0.3, 0.3, 0.3]; // dim white
    let elevations = [30.0_f32.to_radians(), -30.0_f32.to_radians()];
    let radius = 1.0;

    for &el in &elevations {
        let r = radius * el.cos();
        let y = radius * el.sin();

        for i in 0..segments {
            let a0 = (i as f32 / segments as f32) * PI;
            let a1 = ((i + 1) as f32 / segments as f32) * PI;

            verts.push(LineVertex {
                position: [a0.cos() * r, y, a0.sin() * r],
                color,
            });
            verts.push(LineVertex {
                position: [a1.cos() * r, y, a1.sin() * r],
                color,
            });
        }
    }

    verts
}

#[allow(dead_code)]
fn position_to_cartesian(pos: &OrbPosition) -> [f32; 3] {
    let az = pos.azimuth.to_radians();
    let el = pos.elevation.to_radians();
    let r = pos.distance;

    let x = r * el.cos() * az.sin();
    let y = r * el.sin();
    let z = r * el.cos() * az.cos();

    [x, y, z]
}
