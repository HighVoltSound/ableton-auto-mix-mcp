use nih_plug::prelude::{Editor, ParamSetter};
use nih_plug_egui::{create_egui_editor, egui};
use std::sync::Arc;
use crate::StereoEblet3DConcept2Params;

pub struct EditorStateWrapper {
    background_texture: Option<egui::TextureHandle>,
}

pub fn create_editor(
    editor_state: Arc<nih_plug_egui::EguiState>,
    params: Arc<StereoEblet3DConcept2Params>,
) -> Option<Box<dyn Editor>> {
    let initial_state = EditorStateWrapper {
        background_texture: None,
    };

    create_egui_editor(
        editor_state,
        initial_state,
        |ctx, state| {
            // Load the exact user-provided background image
            if state.background_texture.is_none() {
                let image_bytes = include_bytes!("../../assets/background.jpg");
                if let Ok(img) = image::load_from_memory(image_bytes) {
                    let size = [img.width() as usize, img.height() as usize];
                    let image_buffer = img.into_rgba8();
                    let pixels = image_buffer.as_flat_samples();
                    let color_image = egui::ColorImage::from_rgba_unmultiplied(
                        size,
                        pixels.as_slice(),
                    );
                    state.background_texture = Some(ctx.load_texture(
                        "premium_bg",
                        color_image,
                        egui::TextureOptions::LINEAR,
                    ));
                }
            }
        },
        move |ctx, setter, state| {
            egui::CentralPanel::default()
                .frame(egui::Frame::new().inner_margin(0.0)) // Absolutely no margins
                .show(ctx, |ui| {
                    let window_size = egui::vec2(1376.0, 768.0);
                    
                    // 1. Draw absolute pixel-perfect background
                    if let Some(texture) = &state.background_texture {
                        ui.painter().image(
                            texture.id(),
                            egui::Rect::from_min_size(egui::Pos2::ZERO, window_size),
                            egui::Rect::from_min_max(egui::pos2(0.0, 0.0), egui::pos2(1.0, 1.0)),
                            egui::Color32::WHITE,
                        );
                    }
                    
                    // 2. Invisible interaction layer across the entire screen
                    let (_rect, resp) = ui.allocate_exact_size(window_size, egui::Sense::drag());
                    
                    if resp.dragged() {
                        let delta_x = resp.drag_delta().x;
                        let delta_y = resp.drag_delta().y;
                        
                        let new_az = (params.azimuth.value() + delta_x * 0.4).clamp(-90.0, 90.0);
                        let new_el = (params.elevation.value() - delta_y * 0.4).clamp(-45.0, 90.0);
                        
                        setter.begin_set_parameter(&params.azimuth);
                        setter.set_parameter(&params.azimuth, new_az);
                        setter.end_set_parameter(&params.azimuth);
                        
                        setter.begin_set_parameter(&params.elevation);
                        setter.set_parameter(&params.elevation, new_el);
                        setter.end_set_parameter(&params.elevation);
                    }
                    
                    if ui.input(|i| i.raw_scroll_delta.y != 0.0) {
                        let delta = ui.input(|i| i.raw_scroll_delta.y);
                        let new_dist = (params.distance.value() - delta * 0.005).clamp(0.3, 3.0);
                        setter.begin_set_parameter(&params.distance);
                        setter.set_parameter(&params.distance, new_dist);
                        setter.end_set_parameter(&params.distance);
                    }

                    // 3. Premium Minimalist Indicator
                    let center_x = 1376.0 * 0.5;
                    let center_y = 768.0 * 0.5;
                    
                    let az_rad = params.azimuth.value().to_radians();
                    let el_rad = params.elevation.value().to_radians();
                    let dist = params.distance.value();
                    
                    // Radius maps to distance: 0.3m -> ~100px, 3.0m -> ~350px
                    let radius = 100.0 + ((dist - 0.3) / 2.7) * 250.0;
                    
                    // 3D to 2D projection (slight isometric tilt)
                    let orb_x = center_x + (az_rad.sin() * radius);
                    let orb_y = center_y - (el_rad.sin() * radius * 0.7);
                    
                    let painter = ui.painter();
                    let pos = egui::pos2(orb_x, orb_y);
                    let center_pos = egui::pos2(center_x, center_y);

                    // A very elegant, thin connecting line (frosted glass look)
                    painter.line_segment(
                        [center_pos, pos],
                        egui::Stroke::new(1.0_f32, egui::Color32::from_white_alpha(30))
                    );

                    // Outer reticle ring
                    painter.circle_stroke(
                        pos,
                        12.0,
                        egui::Stroke::new(1.0_f32, egui::Color32::from_white_alpha(180))
                    );
                    
                    // Inner precise dot
                    painter.circle_filled(
                        pos,
                        2.5,
                        egui::Color32::WHITE
                    );

                    // Crisp, minimal typography for the HUD
                    let hud_text = format!("AZ: {:>4.1}°\nEL: {:>4.1}°\n D: {:>4.2}m", 
                        params.azimuth.value(), 
                        params.elevation.value(), 
                        dist
                    );
                    
                    painter.text(
                        egui::pos2(orb_x + 20.0, orb_y),
                        egui::Align2::LEFT_CENTER,
                        hud_text,
                        egui::FontId::monospace(11.0),
                        egui::Color32::from_white_alpha(200),
                    );
                });
        },
    )
}
