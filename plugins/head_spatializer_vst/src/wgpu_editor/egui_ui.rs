use egui::{
    Align2, Color32, CornerRadius, FontId, Frame, Margin, Pos2, RichText, Stroke,
    Ui, Vec2,
};
use crate::gui_state::{GuiState, SourceType};

const TEAL: Color32 = Color32::from_rgb(0, 200, 200);
const CORAL: Color32 = Color32::from_rgb(255, 100, 120);
const DARK_BG: Color32 = Color32::from_rgba_premultiplied(18, 18, 28, 220);
const PANEL_BG: Color32 = Color32::from_rgba_premultiplied(25, 25, 38, 200);
const KNOB_BG: Color32 = Color32::from_rgba_premultiplied(35, 35, 50, 230);
const TEXT_DIM: Color32 = Color32::from_rgb(120, 120, 140);
const TEXT_BRIGHT: Color32 = Color32::from_rgb(200, 200, 220);
const ACCENT_PINK: Color32 = Color32::from_rgb(220, 80, 160);

const TOOLTIPS: &[(&str, &str)] = &[
    ("AZIMUTH", "Horizontal angle (-180\u{b0} to 180\u{b0}). Drag or click polar plot to set."),
    ("ELEVATION", "Vertical angle (-90\u{b0} to 90\u{b0}). Positive = above, negative = below."),
    ("ROOM", "Room reverb amount. 0=dry, 1=wet."),
    ("EXT.", "Externalization. 0=in-head, 1=outside head."),
    ("DRY/WET", "Mix between dry and wet signal."),
    ("MONO-MAKER", "Mono below 300Hz for tight low-end."),
    ("ROOM MODEL", "Room acoustics model: Dry/Booth/Studio/Club/Cathedral."),
    ("OUTPUT MODE", "Headphones=binaural, Club=consumer speakers, Hybrid=both."),
    ("DEPTH ZONE", "Depth layer: Front (close), Mid, Back (far)."),
    ("SPLIT SPATIAL", "Per-band stereo width control."),
    ("SUB", "Sub band (20-80Hz) stereo width. 0=mono, 2=extra wide."),
    ("LOW", "Low band (80-300Hz) stereo width."),
    ("MID", "Mid band (300Hz-4kHz) stereo width."),
    ("HIGH", "High band (4kHz+) stereo width."),
];

fn show_tooltip(ui: &mut Ui, name: &str) {
    if let Some((_, text)) = TOOLTIPS.iter().find(|(n, _)| *n == name) {
        ui.label(
            RichText::new(*text)
                .font(FontId::proportional(7.0))
                .color(TEXT_DIM),
        );
    }
}

pub fn draw_ui(ctx: &egui::Context, gui_state: &mut GuiState, scene_tex: egui::TextureId, _screen_size: Vec2, editor_state: Option<&crate::wgpu_editor::WgpuEditorState>) {
    ctx.set_visuals(make_visuals());
    
    // Update CPU usage from shared atomic
    if let Some(state) = editor_state {
        let raw = state.cpu_usage().load(std::sync::atomic::Ordering::Relaxed);
        gui_state.cpu_usage = raw as f32 / 100.0;
    }
    
    draw_scene_background(ctx, scene_tex);
    draw_header(ctx, gui_state);
    draw_distance_slider(ctx, gui_state);
    draw_right_panel(ctx, gui_state);
    draw_bottom_bar(ctx, gui_state);
    draw_preset_browser(ctx, gui_state);
    draw_save_dialog(ctx, gui_state);
    draw_load_dialog(ctx, gui_state);
    draw_help_window(ctx, gui_state);
}

fn make_visuals() -> egui::Visuals {
    let mut vis = egui::Visuals::dark();
    vis.panel_fill = Color32::TRANSPARENT;
    vis.window_fill = PANEL_BG;
    vis.widgets.noninteractive.bg_fill = KNOB_BG;
    vis.widgets.inactive.bg_fill = KNOB_BG;
    vis.widgets.hovered.bg_fill = Color32::from_rgb(45, 45, 65);
    vis.widgets.active.bg_fill = Color32::from_rgb(55, 55, 75);
    vis.widgets.inactive.fg_stroke = Stroke::new(1.0_f32, TEXT_BRIGHT);
    vis.widgets.hovered.fg_stroke = Stroke::new(1.0_f32, TEAL);
    vis.widgets.active.fg_stroke = Stroke::new(1.0_f32, CORAL);
    vis.selection.bg_fill = TEAL.linear_multiply(0.3);
    vis.selection.stroke = Stroke::new(1.0_f32, TEAL);
    vis
}

fn draw_scene_background(ctx: &egui::Context, tex_id: egui::TextureId) {
    egui::CentralPanel::default()
        .frame(Frame::NONE.fill(Color32::TRANSPARENT))
        .show(ctx, |ui| {
            let rect = ui.max_rect();
            ui.painter().image(
                tex_id,
                rect,
                egui::Rect::from_min_max(Pos2::ZERO, Pos2::new(1.0, 1.0)),
                Color32::WHITE,
            );

            // Ambient floating particles
            let time = ui.input(|i| i.time) as f32;
            let painter = ui.painter();
            for i in 0..30 {
                let seed = i as f32 * 127.1;
                let x = ((seed * 0.1 + time * 0.02 * (0.5 + (seed % 3.0) * 0.3)).sin() * 0.5 + 0.5) * rect.width() + rect.left();
                let y = ((seed * 0.3 + time * 0.015 * (0.3 + (seed % 2.0) * 0.4)).cos() * 0.5 + 0.5) * rect.height() + rect.top();
                let size = 1.0 + (seed * 0.7).fract() * 2.0;
                let alpha = 30 + ((time * 0.5 + seed).sin() * 0.5 + 0.5) as u32 * 40;
                let color = Color32::from_rgba_premultiplied(0, 200, 200, alpha as u8);
                painter.add(egui::epaint::CircleShape::filled(Pos2::new(x, y), size, color));
            }
        });
}

fn draw_header(ctx: &egui::Context, gui_state: &mut GuiState) {
    egui::TopBottomPanel::top("header")
        .exact_height(48.0)
        .frame(Frame::NONE.fill(DARK_BG).inner_margin(Margin::symmetric(12, 6)))
        .show(ctx, |ui| {
            ui.horizontal_centered(|ui| {
                ui.spacing_mut().item_spacing.x = 8.0;

                ui.label(
                    RichText::new("S")
                        .font(FontId::proportional(22.0))
                        .color(TEAL)
                        .strong(),
                );
                ui.label(
                    RichText::new("STEREO EBLET 3D")
                        .font(FontId::proportional(16.0))
                        .color(TEXT_BRIGHT)
                        .strong(),
                );
                ui.label(
                    RichText::new("v2.5")
                        .font(FontId::proportional(10.0))
                        .color(TEXT_DIM),
                );

                // CPU meter
                let cpu_pct = (gui_state.cpu_usage * 100.0) as u32;
                let cpu_color = if cpu_pct > 80 { CORAL } else if cpu_pct > 50 { ACCENT_PINK } else { TEAL };
                ui.label(
                    RichText::new(format!("CPU:{}%", cpu_pct))
                        .font(FontId::proportional(8.0))
                        .color(cpu_color),
                );

                ui.add_space(20.0);

                // Genre selector
                ui.label(RichText::new("Genre:").font(FontId::proportional(9.0)).color(TEXT_DIM));
                egui::ComboBox::from_id_salt("genre_combo")
                    .selected_text(gui_state.params.genre.label())
                    .width(80.0)
                    .show_ui(ui, |ui| {
                        for &genre in crate::gui_state::Genre::ALL {
                            if ui.selectable_label(gui_state.params.genre == genre, genre.label()).clicked() {
                                gui_state.params.genre = genre;
                                gui_state.params.apply_genre_source(genre, gui_state.params.source_type);
                                gui_state.params.apply_split_spatial_for_genre();
                            }
                        }
                    });

                // Source selector
                ui.label(RichText::new("Src:").font(FontId::proportional(9.0)).color(TEXT_DIM));
                egui::ComboBox::from_id_salt("source_combo")
                    .selected_text(gui_state.params.source_type.label())
                    .width(70.0)
                    .show_ui(ui, |ui| {
                        for &src in crate::gui_state::SourceType::ALL {
                            if ui.selectable_label(gui_state.params.source_type == src, src.label()).clicked() {
                                gui_state.params.source_type = src;
                                gui_state.params.apply_genre_source(gui_state.params.genre, src);
                            }
                        }
                    });

                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    let bypass_text = if gui_state.params.mix > 0.5 { "ACTIVE" } else { "BYPASS" };
                    let bypass_color = if gui_state.params.mix > 0.5 { TEAL } else { CORAL };
                    if ui.button(RichText::new(bypass_text).color(bypass_color).font(FontId::proportional(10.0))).clicked() {
                        gui_state.params.mix = if gui_state.params.mix > 0.5 { 0.0 } else { 1.0 };
                    }

                    let ab_label = if gui_state.ab.active == 'A' { "A" } else { "B" };
                    if ui.button(RichText::new(format!("A/B:{}", ab_label)).font(FontId::proportional(10.0)).color(TEXT_DIM)).clicked() {
                        gui_state.toggle_ab();
                    }
                    if ui.button(RichText::new("SAVE").font(FontId::proportional(9.0)).color(CORAL)).clicked() {
                        gui_state.snapshot_ab();
                    }
                    if ui.button(RichText::new("RND").font(FontId::proportional(9.0)).color(ACCENT_PINK)).clicked() {
                        gui_state.randomize();
                    }
                    if ui.button(RichText::new("RESET").font(FontId::proportional(9.0)).color(CORAL)).clicked() {
                        gui_state.panic();
                    }
                    if ui.button(RichText::new("PRESETS").font(FontId::proportional(9.0)).color(TEAL)).clicked() {
                        gui_state.show_preset_browser = !gui_state.show_preset_browser;
                    }
                    if ui.button(RichText::new("SAVE FILE").font(FontId::proportional(9.0)).color(ACCENT_PINK)).clicked() {
                        gui_state.show_save_dialog = !gui_state.show_save_dialog;
                    }
                    if ui.button(RichText::new("LOAD FILE").font(FontId::proportional(9.0)).color(ACCENT_PINK)).clicked() {
                        gui_state.show_load_dialog = !gui_state.show_load_dialog;
                    }
                    if ui.button(RichText::new("?").font(FontId::proportional(12.0)).color(TEAL).strong()).clicked() {
                        gui_state.show_help = !gui_state.show_help;
                    }
                });
            });
        });
}

fn draw_distance_slider(ctx: &egui::Context, gui_state: &mut GuiState) {
    egui::SidePanel::left("distance_slider")
        .exact_width(80.0)
        .frame(Frame::NONE.fill(Color32::TRANSPARENT).inner_margin(Margin::same(8)))
        .show(ctx, |ui| {
            ui.vertical_centered(|ui| {
                ui.add_space(60.0);
                ui.label(RichText::new("DISTANCE").font(FontId::proportional(9.0)).color(TEXT_DIM));
                ui.add_space(8.0);

                let desired_height = 300.0;
                let (response, painter) = ui.allocate_painter(Vec2::new(40.0, desired_height), egui::Sense::click_and_drag());

                let rect = response.rect;
                let center_x = rect.center().x;
                let top = rect.top();
                let bottom = rect.bottom();

                painter.line_segment(
                    [Pos2::new(center_x, top), Pos2::new(center_x, bottom)],
                    Stroke::new(2.0_f32, TEXT_DIM),
                );

                let distance = gui_state.params.position.distance;
                let normalized = ((distance - 0.3) / 2.7).clamp(0.0, 1.0);
                let knob_y = bottom - normalized * (desired_height - 20.0) - 10.0;

                painter.add(egui::epaint::CircleShape::filled(Pos2::new(center_x, knob_y), 8.0, ACCENT_PINK));
                painter.add(egui::epaint::CircleShape::stroke(Pos2::new(center_x, knob_y), 10.0, Stroke::new(2.0_f32, TEAL)));

                let labels = [("0.3m", 0.0f32), ("1m", 0.25), ("1.5m", 0.42), ("2.0m", 0.6), ("3.0m", 1.0)];
                for (label, t) in labels {
                    let y = bottom - t * (desired_height - 20.0) - 10.0;
                    painter.text(
                        Pos2::new(center_x + 18.0, y),
                        Align2::LEFT_CENTER,
                        label,
                        FontId::proportional(8.0),
                        TEXT_DIM,
                    );
                }

                if response.dragged() {
                    if let Some(pos) = response.interact_pointer_pos() {
                        let t = ((bottom - pos.y) / (desired_height - 20.0)).clamp(0.0, 1.0);
                        gui_state.params.position.distance = 0.3 + t * 2.7;
                    }
                }
            });
        });
}

fn draw_right_panel(ctx: &egui::Context, gui_state: &mut GuiState) {
    egui::SidePanel::right("right_panel")
        .exact_width(200.0)
        .frame(Frame::NONE.fill(PANEL_BG).inner_margin(Margin::symmetric(10, 10)))
        .show(ctx, |ui| {
            draw_polar_plot(ui, gui_state);
            ui.add_space(6.0);
            draw_knob_row(ui, "AZIMUTH", &mut gui_state.params.position.azimuth, -180.0, 180.0, Some("AZIMUTH"));
            ui.add_space(2.0);
            draw_knob_row(ui, "ELEVATION", &mut gui_state.params.position.elevation, -90.0, 90.0, Some("ELEVATION"));
            ui.add_space(2.0);
            draw_knob_row(ui, "ROOM", &mut gui_state.params.room_amount, 0.0, 1.0, Some("ROOM"));
            ui.add_space(2.0);
            draw_knob_row(ui, "EXT.", &mut gui_state.params.externalization, 0.0, 1.0, Some("EXT."));
            ui.add_space(4.0);
            draw_toggle(ui, "MONO-MAKER", &mut gui_state.params.bass_mono);
            show_tooltip(ui, "MONO-MAKER");
            ui.add_space(4.0);

            // Room model selector
            ui.horizontal(|ui| {
                ui.add_space(4.0);
                ui.label(RichText::new("ROOM:").font(FontId::proportional(8.0)).color(TEXT_DIM));
                for model in crate::gui_state::RoomModel::all() {
                    let is_active = gui_state.params.room == *model;
                    let bg = if is_active { TEAL } else { KNOB_BG };
                    let text_color = if is_active { DARK_BG } else { TEXT_DIM };
                    let btn = ui.add(
                        egui::Button::new(RichText::new(model.label()).font(FontId::proportional(8.0)).color(text_color))
                            .fill(bg)
                            .corner_radius(CornerRadius::same(3))
                            .min_size(Vec2::new(45.0, 18.0)),
                    );
                    if btn.clicked() {
                        gui_state.params.room = *model;
                    }
                }
            });
            show_tooltip(ui, "ROOM MODEL");
            ui.add_space(4.0);

            // Output mode selector
            ui.horizontal(|ui| {
                ui.add_space(4.0);
                ui.label(RichText::new("OUT:").font(FontId::proportional(8.0)).color(TEXT_DIM));
                for &mode in crate::gui_state::OutputMode::ALL {
                    let is_active = gui_state.params.output_mode == mode;
                    let bg = if is_active { TEAL } else { KNOB_BG };
                    let text_color = if is_active { DARK_BG } else { TEXT_DIM };
                    let btn = ui.add(
                        egui::Button::new(RichText::new(mode.label()).font(FontId::proportional(7.0)).color(text_color))
                            .fill(bg)
                            .corner_radius(CornerRadius::same(3))
                            .min_size(Vec2::new(42.0, 16.0)),
                    );
                    if btn.clicked() {
                        gui_state.params.output_mode = mode;
                    }
                }
            });
            show_tooltip(ui, "OUTPUT MODE");
            ui.add_space(2.0);

            // Depth zone selector
            ui.horizontal(|ui| {
                ui.add_space(4.0);
                ui.label(RichText::new("DPTH:").font(FontId::proportional(8.0)).color(TEXT_DIM));
                for &zone in crate::gui_state::DepthZone::ALL {
                    let is_active = gui_state.params.depth_zone == zone;
                    let bg = if is_active { CORAL } else { KNOB_BG };
                    let text_color = if is_active { DARK_BG } else { TEXT_DIM };
                    let btn = ui.add(
                        egui::Button::new(RichText::new(zone.label()).font(FontId::proportional(7.0)).color(text_color))
                            .fill(bg)
                            .corner_radius(CornerRadius::same(3))
                            .min_size(Vec2::new(42.0, 16.0)),
                    );
                    if btn.clicked() {
                        gui_state.params.depth_zone = zone;
                    }
                }
            });
            show_tooltip(ui, "DEPTH ZONE");
            ui.add_space(4.0);

            // Split spatial toggle + width knobs
            draw_toggle(ui, "SPLIT SPATIAL", &mut gui_state.params.split_spatial);
            show_tooltip(ui, "SPLIT SPATIAL");
            if gui_state.params.split_spatial {
                ui.add_space(2.0);
                ui.horizontal(|ui| {
                    ui.add_space(4.0);
                    draw_knob_row(ui, "SUB", &mut gui_state.params.sub_width, 0.0, 2.0, Some("SUB"));
                    draw_knob_row(ui, "LOW", &mut gui_state.params.low_width, 0.0, 2.0, Some("LOW"));
                });
                ui.horizontal(|ui| {
                    ui.add_space(4.0);
                    draw_knob_row(ui, "MID", &mut gui_state.params.mid_width, 0.0, 2.0, Some("MID"));
                    draw_knob_row(ui, "HIGH", &mut gui_state.params.high_width, 0.0, 2.0, Some("HIGH"));
                });
            }
            // MIDI section
            ui.add_space(4.0);
            Frame::NONE
                .fill(KNOB_BG)
                .corner_radius(CornerRadius::same(4))
                .inner_margin(Margin::symmetric(6, 4))
                .show(ui, |ui| {
                    ui.label(RichText::new("MIDI").font(FontId::proportional(8.0)).color(TEAL).strong());
                    ui.label(RichText::new("Use DAW's MIDI Learn").font(FontId::proportional(7.0)).color(TEXT_DIM));
                    ui.label(RichText::new("to assign CCs to params").font(FontId::proportional(7.0)).color(TEXT_DIM));
                });
            ui.add_space(4.0);
            draw_knob_row(ui, "DRY/WET", &mut gui_state.params.mix, 0.0, 1.0, Some("DRY/WET"));
            ui.add_space(12.0);
            draw_side_view(ui, gui_state);
        });
}

fn draw_polar_plot(ui: &mut Ui, gui_state: &mut GuiState) {
    let desired_size = Vec2::new(180.0, 180.0);
    let (response, painter) = ui.allocate_painter(desired_size, egui::Sense::click_and_drag());

    let rect = response.rect;
    let center = rect.center();
    let radius = 80.0;

    // Concentric distance circles
    painter.circle_stroke(center, radius, Stroke::new(1.0_f32, TEXT_DIM));
    painter.circle_stroke(center, radius * 0.66, Stroke::new(0.5_f32, TEXT_DIM));
    painter.circle_stroke(center, radius * 0.33, Stroke::new(0.5_f32, TEXT_DIM));

    // Radial lines + labels
    for angle_deg in [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330] {
        let angle = (angle_deg as f32).to_radians();
        let end = center + Vec2::new(angle.sin(), -angle.cos()) * radius;
        painter.line_segment([center, end], Stroke::new(0.3_f32, TEXT_DIM));

        let label_pos = center + Vec2::new(angle.sin(), -angle.cos()) * (radius + 12.0);
        painter.text(
            label_pos,
            Align2::CENTER_CENTER,
            format!("{}°", angle_deg),
            FontId::proportional(7.0),
            TEXT_DIM,
        );
    }

    // Distance labels inside circles
    painter.text(
        Pos2::new(center.x + radius * 0.33 + 4.0, center.y + 2.0),
        Align2::LEFT_CENTER,
        "0.5",
        FontId::proportional(6.0),
        TEXT_DIM,
    );
    painter.text(
        Pos2::new(center.x + radius * 0.66 + 4.0, center.y + 2.0),
        Align2::LEFT_CENTER,
        "1",
        FontId::proportional(6.0),
        TEXT_DIM,
    );
    painter.text(
        Pos2::new(center.x + radius + 4.0, center.y + 2.0),
        Align2::LEFT_CENTER,
        "2m",
        FontId::proportional(6.0),
        TEXT_DIM,
    );

    // Head silhouette at center (small circle)
    painter.circle_filled(center, 8.0, Color32::from_rgba_premultiplied(60, 60, 80, 180));
    painter.circle_stroke(center, 8.0, Stroke::new(1.0_f32, TEXT_DIM));

    // Orb position
    let az = gui_state.params.position.azimuth.to_radians();
    let dist_norm = (gui_state.params.position.distance / 3.0).clamp(0.0, 1.0);
    let r = dist_norm * radius;
    let orb_pos = center + Vec2::new(az.sin() * r, -az.cos() * r);

    // Glow ring
    painter.add(egui::epaint::CircleShape::stroke(orb_pos, 10.0, Stroke::new(3.0_f32, ACCENT_PINK.linear_multiply(0.3))));
    // Solid orb
    painter.add(egui::epaint::CircleShape::filled(orb_pos, 5.0, ACCENT_PINK));
    painter.add(egui::epaint::CircleShape::stroke(orb_pos, 7.0, Stroke::new(1.5_f32, TEAL)));

    // Dotted line from head to orb
    let steps = 12;
    for i in 0..steps {
        let t = i as f32 / steps as f32;
        let p = center.lerp(orb_pos, t);
        if i % 2 == 0 {
            painter.add(egui::epaint::CircleShape::filled(p, 1.0, TEXT_DIM.linear_multiply(0.5)));
        }
    }

    // Handle click/drag to set position
    if response.dragged() || response.clicked() {
        if let Some(pos) = response.interact_pointer_pos() {
            let delta = pos - center;
            let new_az = delta.x.atan2(-delta.y).to_degrees();
            let new_dist = (delta.length() / radius * 3.0).clamp(0.3, 3.0);
            gui_state.params.position.azimuth = new_az.clamp(-180.0, 180.0);
            gui_state.params.position.distance = new_dist;
        }
    }

    // Title
    painter.text(
        Pos2::new(center.x, center.y - radius - 18.0),
        Align2::CENTER_CENTER,
        "90°",
        FontId::proportional(8.0),
        TEXT_DIM,
    );
}

fn draw_knob_row(ui: &mut Ui, label: &str, value: &mut f32, min: f32, max: f32, tooltip: Option<&str>) {
    ui.vertical(|ui| {
        ui.horizontal(|ui| {
            ui.add_space(4.0);

            let knob_size = 44.0;
            let desired = Vec2::splat(knob_size);
            let (response, painter) = ui.allocate_painter(desired, egui::Sense::click_and_drag());

            let rect = response.rect;
            let center = rect.center();
            let knob_radius = 16.0;

            // Outer glow ring
            painter.circle_stroke(center, knob_radius + 3.0, Stroke::new(4.0_f32, TEAL.linear_multiply(0.15)));

            // Background circle
            painter.circle_filled(center, knob_radius, KNOB_BG);
            painter.circle_stroke(center, knob_radius, Stroke::new(1.0_f32, TEXT_DIM.linear_multiply(0.3)));

            // Value arc with glow
            let normalized = (*value - min) / (max - min);
            let start_angle = std::f32::consts::PI * 0.75;
            let sweep = normalized * std::f32::consts::PI * 1.5;
            let end_angle = start_angle + sweep;

            // Glow layer (wider, transparent)
            let glow_points: Vec<Pos2> = (0..24)
                .map(|i| {
                    let t = i as f32 / 23.0;
                    let angle = start_angle + t * sweep;
                    center + Vec2::new(angle.cos(), -angle.sin()) * (knob_radius + 1.0)
                })
                .collect();
            painter.add(egui::epaint::PathShape::line(glow_points, Stroke::new(6.0_f32, TEAL.linear_multiply(0.25))));

            // Solid arc
            let arc_points: Vec<Pos2> = (0..24)
                .map(|i| {
                    let t = i as f32 / 23.0;
                    let angle = start_angle + t * sweep;
                    center + Vec2::new(angle.cos(), -angle.sin()) * knob_radius
                })
                .collect();
            painter.add(egui::epaint::PathShape::line(arc_points, Stroke::new(2.5_f32, TEAL)));

            // Indicator dot at end of arc
            let indicator_pos = center + Vec2::new(end_angle.cos(), -end_angle.sin()) * knob_radius;
            painter.add(egui::epaint::CircleShape::filled(indicator_pos, 3.0, TEXT_BRIGHT));

            // Value text below knob
            let display = if max > 10.0 {
                format!("{:.0}\u{b0}", value)
            } else {
                format!("{:.2}", value)
            };
            painter.text(
                Pos2::new(center.x, center.y + knob_radius + 14.0),
                Align2::CENTER_CENTER,
                display,
                FontId::proportional(9.0),
                TEXT_BRIGHT,
            );

            // Label below value
            painter.text(
                Pos2::new(center.x, center.y + knob_radius + 26.0),
                Align2::CENTER_CENTER,
                label,
                FontId::proportional(7.0),
                TEXT_DIM,
            );

            if response.dragged() {
                let delta = response.drag_delta().x / knob_size * (max - min) * 2.0;
                *value = (*value + delta).clamp(min, max);
            }
        });
        if let Some(tip) = tooltip {
            show_tooltip(ui, tip);
        }
    });
}

fn draw_toggle(ui: &mut Ui, label: &str, value: &mut bool) {
    ui.horizontal(|ui| {
        ui.add_space(4.0);
        let toggle_size = Vec2::new(36.0, 18.0);
        let (response, painter) = ui.allocate_painter(toggle_size, egui::Sense::click());

        let rect = response.rect;
        let bg_color = if *value { TEAL } else { KNOB_BG };
        painter.rect(rect, CornerRadius::same(9), bg_color, Stroke::new(1.0_f32, TEXT_DIM), egui::StrokeKind::Inside);

        let knob_x = if *value { rect.right() - 9.0 } else { rect.left() + 9.0 };
        painter.add(egui::epaint::CircleShape::filled(Pos2::new(knob_x, rect.center().y), 7.0, TEXT_BRIGHT));

        if response.clicked() {
            *value = !*value;
        }

        ui.add_space(6.0);
        ui.label(RichText::new(label).font(FontId::proportional(8.0)).color(TEXT_DIM));
    });
}

fn draw_side_view(ui: &mut Ui, gui_state: &GuiState) {
    let desired_size = Vec2::new(180.0, 120.0);
    let (response, painter) = ui.allocate_painter(desired_size, egui::Sense::hover());

    let rect = response.rect;
    let center = rect.center();

    // Head silhouette - more detailed profile
    let head_points: Vec<Pos2> = vec![
        Pos2::new(center.x - 20.0, center.y + 30.0), // chin
        Pos2::new(center.x - 25.0, center.y + 15.0), // jaw
        Pos2::new(center.x - 28.0, center.y + 5.0),  // cheek
        Pos2::new(center.x - 26.0, center.y - 8.0),  // temple
        Pos2::new(center.x - 20.0, center.y - 20.0), // forehead
        Pos2::new(center.x - 10.0, center.y - 30.0), // top
        Pos2::new(center.x + 5.0, center.y - 35.0),  // crown
        Pos2::new(center.x + 20.0, center.y - 30.0), // back top
        Pos2::new(center.x + 28.0, center.y - 18.0), // back
        Pos2::new(center.x + 30.0, center.y - 5.0),  // occiput
        Pos2::new(center.x + 28.0, center.y + 8.0),  // neck
        Pos2::new(center.x + 22.0, center.y + 20.0), // neck base
        Pos2::new(center.x + 10.0, center.y + 28.0), // shoulder
        Pos2::new(center.x - 20.0, center.y + 30.0), // close
    ];

    // Glow outline
    painter.add(egui::epaint::PathShape::line(
        head_points.clone(),
        Stroke::new(4.0_f32, TEAL.linear_multiply(0.15)),
    ));
    // Solid outline
    painter.add(egui::epaint::PathShape::line(head_points, Stroke::new(1.5_f32, TEAL)));

    // Ear detail
    let ear_center = Pos2::new(center.x + 28.0, center.y - 5.0);
    painter.add(egui::epaint::CircleShape::stroke(ear_center, 6.0, Stroke::new(1.0_f32, TEXT_DIM)));

    // Eye detail
    let eye_pos = Pos2::new(center.x - 22.0, center.y - 12.0);
    painter.add(egui::epaint::CircleShape::filled(eye_pos, 2.0, TEAL));

    // Elevation dot with glow
    let elevation_norm = (gui_state.params.position.elevation + 90.0) / 180.0;
    let dot_y = rect.top() + 10.0 + (1.0 - elevation_norm) * (rect.height() - 20.0);
    let dot_pos = Pos2::new(center.x - 30.0, dot_y);

    // Glow ring
    painter.add(egui::epaint::CircleShape::stroke(dot_pos, 8.0, Stroke::new(3.0_f32, ACCENT_PINK.linear_multiply(0.3))));
    // Solid dot
    painter.add(egui::epaint::CircleShape::filled(dot_pos, 4.0, ACCENT_PINK));

    // Vertical line from dot to head
    painter.line_segment(
        [dot_pos, Pos2::new(center.x - 20.0, dot_y)],
        Stroke::new(0.5_f32, TEXT_DIM.linear_multiply(0.3)),
    );

    // Side labels
    let side_labels = [("+90°", 0.05f32), ("+30°", 0.33), ("0°", 0.58), ("-45°", 0.88)];
    for (label, t) in side_labels {
        let y = rect.top() + t * rect.height();
        painter.text(
            Pos2::new(rect.right() - 5.0, y),
            Align2::RIGHT_CENTER,
            label,
            FontId::proportional(7.0),
            TEXT_DIM,
        );
    }
}

fn draw_preset_browser(ctx: &egui::Context, gui_state: &mut GuiState) {
    if !gui_state.show_preset_browser { return; }

    egui::Window::new("PRESETS")
        .collapsible(false)
        .resizable(false)
        .default_width(350.0)
        .default_height(400.0)
        .frame(Frame::NONE.fill(PANEL_BG).corner_radius(CornerRadius::same(8)).inner_margin(Margin::symmetric(12, 12)).stroke(Stroke::new(1.0_f32, TEAL)))
        .show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.label(RichText::new("Search:").font(FontId::proportional(10.0)).color(TEXT_DIM));
                let mut search = gui_state.preset_search.clone();
                ui.add(egui::TextEdit::singleline(&mut search).desired_width(200.0).font(FontId::proportional(10.0)));
                gui_state.preset_search = search;
                ui.add_space(8.0);
                if ui.button(RichText::new("Close").font(FontId::proportional(10.0)).color(CORAL)).clicked() {
                    gui_state.show_preset_browser = false;
                }
            });
            ui.add_space(8.0);
            ui.separator();
            ui.add_space(4.0);

            egui::ScrollArea::vertical().max_height(340.0).show(ui, |ui| {
                let search_lower = gui_state.preset_search.to_lowercase();
                for (i, preset) in crate::gui_state::PRESETS.iter().enumerate() {
                    if !search_lower.is_empty() && !preset.name.to_lowercase().contains(&search_lower) {
                        continue;
                    }
                    let is_active = gui_state.preset_index == i;
                    let bg = if is_active { TEAL } else { KNOB_BG };
                    let text_color = if is_active { DARK_BG } else { TEXT_BRIGHT };

                    let btn = ui.add(
                        egui::Button::new(RichText::new(preset.name).font(FontId::proportional(10.0)).color(text_color))
                            .fill(bg)
                            .corner_radius(CornerRadius::same(4))
                            .min_size(Vec2::new(320.0, 22.0)),
                    );
                    if btn.clicked() {
                        gui_state.load_preset(i);
                        gui_state.show_preset_browser = false;
                    }
                }
            });
        });
}

fn draw_save_dialog(ctx: &egui::Context, gui_state: &mut GuiState) {
    if !gui_state.show_save_dialog { return; }
    
    egui::Window::new("SAVE PRESET")
        .collapsible(false)
        .resizable(false)
        .default_width(300.0)
        .frame(Frame::NONE.fill(PANEL_BG).corner_radius(CornerRadius::same(8)).inner_margin(Margin::symmetric(12, 12)).stroke(Stroke::new(1.0_f32, TEAL)))
        .show(ctx, |ui| {
            ui.label(RichText::new("Preset name:").font(FontId::proportional(10.0)).color(TEXT_DIM));
            ui.add(egui::TextEdit::singleline(&mut gui_state.preset_name_input).desired_width(250.0).font(FontId::proportional(10.0)));
            ui.add_space(8.0);
            ui.horizontal(|ui| {
                if ui.button(RichText::new("Save").font(FontId::proportional(10.0)).color(TEAL)).clicked() {
                    let name = gui_state.preset_name_input.clone();
                    if !name.is_empty() {
                        let _ = gui_state.save_preset_to_file(&name);
                        gui_state.show_save_dialog = false;
                    }
                }
                if ui.button(RichText::new("Cancel").font(FontId::proportional(10.0)).color(CORAL)).clicked() {
                    gui_state.show_save_dialog = false;
                }
            });
        });
}

fn draw_load_dialog(ctx: &egui::Context, gui_state: &mut GuiState) {
    if !gui_state.show_load_dialog { return; }
    
    egui::Window::new("LOAD PRESET")
        .collapsible(false)
        .resizable(false)
        .default_width(300.0)
        .default_height(350.0)
        .frame(Frame::NONE.fill(PANEL_BG).corner_radius(CornerRadius::same(8)).inner_margin(Margin::symmetric(12, 12)).stroke(Stroke::new(1.0_f32, TEAL)))
        .show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.label(RichText::new("Saved Presets:").font(FontId::proportional(10.0)).color(TEXT_BRIGHT));
                if ui.button(RichText::new("Close").font(FontId::proportional(9.0)).color(CORAL)).clicked() {
                    gui_state.show_load_dialog = false;
                }
            });
            ui.add_space(4.0);
            ui.separator();
            ui.add_space(4.0);
            
            let presets = gui_state.list_saved_presets();
            egui::ScrollArea::vertical().max_height(280.0).show(ui, |ui| {
                if presets.is_empty() {
                    ui.label(RichText::new("No saved presets found").font(FontId::proportional(9.0)).color(TEXT_DIM));
                }
                for name in &presets {
                    let btn = ui.add(
                        egui::Button::new(RichText::new(name).font(FontId::proportional(10.0)).color(TEXT_BRIGHT))
                            .fill(KNOB_BG)
                            .corner_radius(CornerRadius::same(4))
                            .min_size(Vec2::new(260.0, 22.0)),
                    );
                    if btn.clicked() {
                        let _ = gui_state.load_preset_from_file(name);
                        gui_state.show_load_dialog = false;
                    }
                }
            });
        });
}

fn draw_help_window(ctx: &egui::Context, gui_state: &mut GuiState) {
    if !gui_state.show_help { return; }
    
    egui::Window::new("STEREO EBLET 3D - Help")
        .collapsible(false)
        .resizable(false)
        .default_width(420.0)
        .default_height(480.0)
        .frame(Frame::NONE.fill(PANEL_BG).corner_radius(CornerRadius::same(8)).inner_margin(Margin::symmetric(14, 14)).stroke(Stroke::new(1.0_f32, TEAL)))
        .show(ctx, |ui| {
            ui.heading(RichText::new("STEREO EBLET 3D v2.5").font(FontId::proportional(14.0)).color(TEAL));
            ui.label(RichText::new("Binaural 3D Head Spatializer & Psychoacoustic Plugin").font(FontId::proportional(9.0)).color(TEXT_DIM));
            ui.add_space(8.0);
            ui.separator();
            ui.add_space(6.0);
            
            ui.label(RichText::new("CONTROLS").font(FontId::proportional(10.0)).color(TEAL).strong());
            ui.add_space(2.0);
            let controls = [
                ("Polar Plot", "Click/drag to set azimuth + distance"),
                ("3D Head", "Drag orb to position sound source"),
                ("Azimuth", "Horizontal angle -180 to 180 degrees"),
                ("Elevation", "Vertical angle -90 to 90 degrees"),
                ("Room", "Room reverb amount 0-100%"),
                ("Ext.", "Externalization: 0=in-head, 1=outside"),
                ("Dry/Wet", "Mix between dry and wet signal"),
                ("Mono-Maker", "Mono below 300Hz for tight low end"),
                ("Room Model", "Dry, Booth, Studio, Club, Cathedral"),
                ("Output Mode", "Headphones, Club, Hybrid"),
                ("Depth Zone", "Front (close), Mid, Back (far)"),
                ("Split Spatial", "Per-band width: Sub/Low/Mid/High"),
            ];
            for (name, desc) in controls {
                ui.horizontal(|ui| {
                    ui.label(RichText::new(name).font(FontId::proportional(9.0)).color(TEXT_BRIGHT).strong());
                    ui.label(RichText::new(desc).font(FontId::proportional(8.0)).color(TEXT_DIM));
                });
            }
            
            ui.add_space(6.0);
            ui.label(RichText::new("KEYBOARD SHORTCUTS").font(FontId::proportional(10.0)).color(TEAL).strong());
            ui.add_space(2.0);
            let shortcuts = [
                ("Arrow Left/Right", "Cycle Genre"),
                ("Arrow Up/Down", "Cycle Source Type"),
                ("1 / 2 / 3", "Depth Zone: Front / Mid / Back"),
                ("Tab", "Toggle Split Spatial"),
                ("H / C / Y", "Output Mode: Headphones / Club / Hybrid"),
                ("E / Q", "Increase / Decrease Externalization"),
            ];
            for (key, action) in shortcuts {
                ui.horizontal(|ui| {
                    ui.label(RichText::new(key).font(FontId::proportional(9.0)).color(ACCENT_PINK).strong());
                    ui.label(RichText::new(action).font(FontId::proportional(8.0)).color(TEXT_DIM));
                });
            }
            
            ui.add_space(6.0);
            ui.label(RichText::new("DSP FEATURES").font(FontId::proportional(10.0)).color(TEAL).strong());
            ui.add_space(2.0);
            let features = [
                "Binaural ITD (interaural time difference)",
                "ILD (interaural level difference)",
                "Pinna filtering (HRTF approximation)",
                "Room reflections (early + late)",
                "Split-band spatialization (4 bands)",
                "Externalization (decorrelated taps)",
                "Genre-aware spatial templates",
                "55 instrument presets",
            ];
            for feat in features {
                ui.label(RichText::new(format!("  {}", feat)).font(FontId::proportional(8.0)).color(TEXT_DIM));
            }
            
            ui.add_space(10.0);
            ui.horizontal(|ui| {
                if ui.button(RichText::new("Close").font(FontId::proportional(10.0)).color(TEAL)).clicked() {
                    gui_state.show_help = false;
                }
            });
        });
}

fn draw_bottom_bar(ctx: &egui::Context, gui_state: &mut GuiState) {
    egui::TopBottomPanel::bottom("bottom_bar")
        .exact_height(44.0)
        .frame(Frame::NONE.fill(DARK_BG).inner_margin(Margin::symmetric(12, 6)))
        .show(ctx, |ui| {
            ui.horizontal_centered(|ui| {
                ui.label(RichText::new("INSTRUMENT").font(FontId::proportional(9.0)).color(TEXT_DIM));
                ui.add_space(8.0);

                let presets = [
                    ("Kick", SourceType::Kick),
                    ("Bass", SourceType::Bass),
                    ("Hat", SourceType::Hat),
                    ("Lead", SourceType::Lead),
                    ("Pad", SourceType::Pad),
                    ("Vocal", SourceType::Vocal),
                    ("Perc", SourceType::Perc),
                    ("FX", SourceType::Fx),
                ];

                for (label, source) in presets {
                    let is_active = gui_state.params.source_type == source;
                    let bg = if is_active { TEAL } else { KNOB_BG };
                    let text_color = if is_active { DARK_BG } else { TEXT_DIM };

                    let btn = ui.add(
                        egui::Button::new(RichText::new(label).font(FontId::proportional(10.0)).color(text_color))
                            .fill(bg)
                            .corner_radius(CornerRadius::same(4))
                            .min_size(Vec2::new(60.0, 28.0)),
                    );

                    if btn.clicked() {
                        gui_state.params.source_type = source;
                        gui_state.params.apply_genre_source(gui_state.params.genre, source);
                    }

                    ui.add_space(4.0);
                }
            });
        });
}
