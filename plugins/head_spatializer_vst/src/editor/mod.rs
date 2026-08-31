use nih_plug_egui::egui::{self, pos2, Color32, Pos2, Rect, RichText, Stroke, Vec2};
use std::sync::Arc;

use crate::gui_state::{GuiState, PRESETS, RoomModel};

mod knob;

const BG_COLOR: Color32 = Color32::from_rgb(10, 10, 26);
const TEAL: Color32 = Color32::from_rgb(15, 240, 252);
const CORAL: Color32 = Color32::from_rgb(255, 107, 53);
const VIOLET: Color32 = Color32::from_rgb(124, 58, 237);
const TEXT_DIM: Color32 = Color32::from_rgba_premultiplied(255, 255, 255, 128);
const TEXT_BRIGHT: Color32 = Color32::WHITE;

pub struct EditorState {
    pub gui: GuiState,
}

impl EditorState {
    pub fn new() -> Self {
        Self {
            gui: GuiState::new(),
        }
    }
}

impl Default for EditorState {
    fn default() -> Self {
        Self::new()
    }
}

pub fn create_editor(
    egui_state: Arc<nih_plug_egui::EguiState>,
) -> Option<Box<dyn nih_plug::prelude::Editor>> {
    let state = EditorState::new();

    nih_plug_egui::create_egui_editor(
        egui_state,
        state,
        |ctx, _state| {
            let mut style = (*ctx.style()).clone();
            style.spacing.item_spacing = Vec2::new(8.0, 6.0);
            ctx.set_style(style);
        },
        |ctx, _setter, state| {
            egui::CentralPanel::default()
                .frame(egui::Frame::NONE.fill(BG_COLOR))
                .show(ctx, |ui| {
                    draw_header(ui, state);
                    ui.add_space(4.0);
                    draw_main_area(ui, state);
                    ui.add_space(4.0);
                    draw_preset_bar(ui, state);
                });
        },
    )
}

fn draw_header(ui: &mut egui::Ui, state: &mut EditorState) {
    ui.horizontal(|ui| {
        ui.add_space(8.0);

        ui.label(
            RichText::new("⬡ STEREO EBLET 3D v2.5")
                .color(TEAL)
                .size(14.0)
                .strong(),
        );

        ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
            let ab_text = if state.gui.ab.active == 'A' { "B" } else { "A" };
            let ab_color = if state.gui.ab.active == 'A' {
                VIOLET
            } else {
                CORAL
            };
            if ui
                .button(
                    RichText::new(format!("A/B →{}", ab_text))
                        .color(ab_color)
                        .size(11.0),
                )
                .on_hover_text("Toggle A/B compare")
                .clicked()
            {
                state.gui.toggle_ab();
            }

            let bypass_color = if state.gui.bypassed { CORAL } else { TEXT_DIM };
            if ui
                .button(
                    RichText::new("BYPASS")
                        .color(bypass_color)
                        .size(11.0),
                )
                .clicked()
            {
                state.gui.bypassed = !state.gui.bypassed;
            }

            ui.add_space(16.0);

            if ui
                .button(RichText::new("◄").color(TEAL).size(13.0))
                .clicked()
            {
                state.gui.prev_preset();
            }
            ui.label(
                RichText::new(PRESETS[state.gui.preset_index].name)
                    .color(TEXT_BRIGHT)
                    .size(12.0),
            );
            if ui
                .button(RichText::new("►").color(TEAL).size(13.0))
                .clicked()
            {
                state.gui.next_preset();
            }
        });
    });
}

fn draw_main_area(ui: &mut egui::Ui, state: &mut EditorState) {
    ui.horizontal(|ui| {
        ui.add_space(8.0);

        draw_distance_slider(ui, state);

        ui.add_space(8.0);

        ui.vertical(|ui| {
            let available = ui.available_size();
            let canvas_height = available.y - 20.0;
            let canvas_width = available.x * 0.55;

            draw_3d_canvas(ui, state, canvas_width, canvas_height);
        });

        ui.add_space(8.0);

        ui.vertical(|ui| {
            ui.label(RichText::new("RADAR TOP").color(TEXT_DIM).size(9.0));
            draw_radar_view(ui, state, 120.0, 120.0);

            ui.add_space(8.0);

            ui.label(RichText::new("SIDE ELEV").color(TEXT_DIM).size(9.0));
            draw_elevation_view(ui, state, 120.0, 100.0);
        });

        ui.add_space(8.0);

        draw_knobs_column(ui, state);

        ui.add_space(8.0);
    });
}

fn draw_distance_slider(ui: &mut egui::Ui, state: &mut EditorState) {
    ui.vertical(|ui| {
        ui.label(RichText::new("DIST").color(TEXT_DIM).size(9.0));

        let slider_height = 200.0;
        let slider_width = 24.0;
        let (rect, response) =
            ui.allocate_at_least(Vec2::new(slider_width, slider_height), egui::Sense::click_and_drag());

        if ui.is_rect_visible(rect) {
            let painter = ui.painter();

            let bg = Color32::from_rgba_premultiplied(30, 30, 50, 200);
            painter.rect_filled(rect, 4.0, bg);

            let norm = (state.gui.params.position.distance - 0.3) / (3.0 - 0.3);
            let handle_y = rect.max.y - norm * slider_height;
            let handle_color = if norm < 0.3 { TEAL } else { CORAL };
            let handle_radius = 6.0 + (1.0 - norm) * 4.0;

            painter.circle_filled(
                pos2(rect.center().x, handle_y),
                handle_radius,
                handle_color,
            );

            let glow_alpha = (80.0 + (1.0 - norm) * 100.0) as u8;
            painter.circle_filled(
                pos2(rect.center().x, handle_y),
                handle_radius + 4.0,
                Color32::from_rgba_premultiplied(15, 240, 252, glow_alpha),
            );
        }

        if response.dragged() {
            let mouse_y = response.interact_pointer_pos().unwrap().y;
            let norm = 1.0 - ((mouse_y - rect.min.y) / slider_height).clamp(0.0, 1.0);
            state.gui.params.position.distance = 0.3 + norm * (3.0 - 0.3);
        }

        ui.add_space(4.0);
        ui.label(
            RichText::new(format!("{:.1}m", state.gui.params.position.distance))
                .color(TEXT_BRIGHT)
                .size(10.0),
        );
        ui.label(RichText::new("close").color(TEXT_DIM).size(8.0));
    });
}

fn draw_3d_canvas(ui: &mut egui::Ui, state: &mut EditorState, width: f32, height: f32) {
    let (rect, response) = ui.allocate_at_least(Vec2::new(width, height), egui::Sense::click_and_drag());

    if ui.is_rect_visible(rect) {
        let painter = ui.painter();
        let bg = Color32::from_rgba_premultiplied(8, 8, 20, 240);
        painter.rect_filled(rect, 8.0, bg);

        let border = Stroke::new(1.0_f32, Color32::from_rgba_premultiplied(15, 240, 252, 60));
        painter.rect_stroke(rect, 8.0, border, egui::StrokeKind::Middle);

        let center = rect.center();
        let dome_radius = height * 0.35;

        draw_dome_wireframe(painter, center, dome_radius);
        draw_head_silhouette(painter, center);
        draw_orb_on_dome(painter, center, dome_radius, state);
        draw_distance_rings_on_floor(painter, center, height, state);
        draw_latitude_markings(painter, center, dome_radius);
        draw_beam_to_ear(painter, center, dome_radius, state);
    }

    if response.dragged() {
        let mouse_pos = response.interact_pointer_pos().unwrap();
        let center = rect.center();
        let dx = (mouse_pos.x - center.x) / (rect.width() * 0.5);
        let dy = (center.y - mouse_pos.y) / (rect.height() * 0.5);

        state.gui.params.position.azimuth = (dx * 90.0).clamp(-90.0, 90.0);
        state.gui.params.position.elevation = (dy * 90.0).clamp(-45.0, 90.0);
    }
}

fn draw_dome_wireframe(painter: &egui::Painter, center: Pos2, radius: f32) {
    let dome_color = Color32::from_rgba_premultiplied(15, 240, 252, 40);
    let segments = 48;

    let mut dome_points = Vec::with_capacity(segments + 1);
    for i in 0..=segments {
        let t = i as f32 / segments as f32;
        let angle = std::f32::consts::PI + t * std::f32::consts::PI;
        let x = center.x + radius * angle.cos();
        let y = center.y - radius * 0.6 * angle.sin();
        dome_points.push(pos2(x, y));
    }

    for window in dome_points.windows(2) {
        painter.line_segment(
            [window[0], window[1]],
                Stroke::new(1.0_f32, dome_color),
        );
    }

    for i in 1..4 {
        let ring_radius = radius * (i as f32 / 4.0);
        let mut ring_points = Vec::with_capacity(segments + 1);
        for j in 0..=segments {
            let t = j as f32 / segments as f32;
            let angle = std::f32::consts::PI + t * std::f32::consts::PI;
            let x = center.x + ring_radius * angle.cos();
            let y = center.y - radius * 0.6 * (angle.sin() * (i as f32 / 4.0));
            ring_points.push(pos2(x, y));
        }
        for window in ring_points.windows(2) {
            painter.line_segment(
                [window[0], window[1]],
                Stroke::new(0.5_f32, Color32::from_rgba_premultiplied(15, 240, 252, 20)),
            );
        }
    }
}

fn draw_head_silhouette(painter: &egui::Painter, center: Pos2) {
    let head_color = Color32::from_rgba_premultiplied(15, 240, 252, 30);
    let outline_color = Color32::from_rgba_premultiplied(15, 240, 252, 80);

    let head_center = pos2(center.x, center.y + 10.0);
    let head_width = 22.0;
    let head_height = 30.0;

    let mut head_points = Vec::new();
    let segments = 32;
    for i in 0..=segments {
        let t = i as f32 / segments as f32;
        let angle = t * std::f32::consts::PI * 2.0;
        let wobble = 1.0 + 0.1 * (angle * 3.0).sin();
        let x = head_center.x + head_width * wobble * angle.cos();
        let y = head_center.y + head_height * wobble * angle.sin();
        head_points.push(pos2(x, y));
    }

    for window in head_points.windows(2) {
        painter.line_segment([window[0], window[1]], Stroke::new(1.0_f32, outline_color));
    }

    let ear_x = head_center.x + head_width * 0.9;
    let ear_y = head_center.y;
    painter.circle_filled(pos2(ear_x, ear_y), 4.0, head_color);
    painter.circle_stroke(pos2(ear_x, ear_y), 4.0, Stroke::new(1.0_f32, outline_color));

    let ear_x_left = head_center.x - head_width * 0.9;
    painter.circle_filled(pos2(ear_x_left, ear_y), 4.0, head_color);
    painter.circle_stroke(pos2(ear_x_left, ear_y), 4.0, Stroke::new(1.0_f32, outline_color));
}

fn draw_orb_on_dome(painter: &egui::Painter, center: Pos2, radius: f32, state: &EditorState) {
    let az_norm = (state.gui.params.position.azimuth + 90.0) / 180.0;
    let el_norm = (state.gui.params.position.elevation + 45.0) / 135.0;

    let angle = std::f32::consts::PI + az_norm * std::f32::consts::PI;
    let orb_x = center.x + radius * 0.8 * angle.cos();
    let orb_y = center.y - radius * 0.6 * el_norm;

    let orb_radius = 8.0;
    let glow_radius = orb_radius + 6.0;

    painter.circle_filled(
        pos2(orb_x, orb_y),
        glow_radius,
        Color32::from_rgba_premultiplied(255, 107, 53, 40),
    );
    painter.circle_filled(pos2(orb_x, orb_y), orb_radius, CORAL);
    painter.circle_filled(
        pos2(orb_x - 2.0, orb_y - 2.0),
        2.0,
        Color32::from_rgba_premultiplied(255, 200, 150, 200),
    );

    let wave_color = Color32::from_rgba_premultiplied(255, 107, 53, 30);
    for i in 1..=3 {
        let wave_r = orb_radius + i as f32 * 8.0;
        painter.circle_stroke(
            pos2(orb_x, orb_y),
            wave_r,
            Stroke::new(1.0_f32, wave_color),
        );
    }
}

fn draw_distance_rings_on_floor(painter: &egui::Painter, center: Pos2, height: f32, _state: &EditorState) {
    let floor_y = center.y + height * 0.35;
    let ring_color = Color32::from_rgba_premultiplied(15, 240, 252, 25);

    let distances: [f32; 4] = [0.5, 1.0, 2.0, 3.0];
    let max_width = 100.0;

    for &d in &distances {
        let norm: f32 = (d - 0.3) / (3.0 - 0.3);
        let log_norm = (norm.ln() / 3.0_f32.ln()).clamp(0.0, 1.0);
        let ring_width = log_norm * max_width;

        let left = pos2(center.x - ring_width, floor_y);
        let right = pos2(center.x + ring_width, floor_y);
        painter.line_segment([left, right], Stroke::new(0.5_f32, ring_color));

        painter.text(
            pos2(center.x + ring_width + 4.0, floor_y),
            egui::Align2::LEFT_CENTER,
            format!("{}m", d),
            egui::FontId::proportional(8.0),
            TEXT_DIM,
        );
    }
}

fn draw_latitude_markings(painter: &egui::Painter, center: Pos2, radius: f32) {
    let marking_color = Color32::from_rgba_premultiplied(15, 240, 252, 40);
    let angles: [f32; 5] = [15.0, 30.0, 45.0, 60.0, 75.0];

    for &deg in &angles {
        let rad: f32 = deg.to_radians();
        let y_offset = radius * 0.6 * (rad / (std::f32::consts::PI * 0.5)).min(1.0);
        let x_offset = radius * 0.3 * (1.0 - deg / 90.0);

        let mark_pos = pos2(center.x + x_offset + 10.0, center.y - y_offset);
        painter.text(
            mark_pos,
            egui::Align2::LEFT_CENTER,
            format!("+{}°", deg),
            egui::FontId::proportional(7.0),
            marking_color,
        );
    }
}

fn draw_beam_to_ear(painter: &egui::Painter, center: Pos2, radius: f32, state: &EditorState) {
    let az_norm = (state.gui.params.position.azimuth + 90.0) / 180.0;
    let el_norm = (state.gui.params.position.elevation + 45.0) / 135.0;

    let angle = std::f32::consts::PI + az_norm * std::f32::consts::PI;
    let orb_x = center.x + radius * 0.8 * angle.cos();
    let orb_y = center.y - radius * 0.6 * el_norm;

    let ear_x = if state.gui.params.position.azimuth >= 0.0 {
        center.x + 20.0
    } else {
        center.x - 20.0
    };
    let ear_y = center.y + 10.0;

    let beam_color = Color32::from_rgba_premultiplied(255, 107, 53, 80);
    let dash_len = 4.0;
    let gap_len = 4.0;

    let dx = ear_x - orb_x;
    let dy = ear_y - orb_y;
    let dist = (dx * dx + dy * dy).sqrt();
    let steps = (dist / (dash_len + gap_len)) as usize;

    for i in 0..steps {
        let t_start = i as f32 / steps as f32;
        let t_end = (i as f32 + 0.5) / steps as f32;

        let start = pos2(
            orb_x + dx * t_start,
            orb_y + dy * t_start,
        );
        let end = pos2(
            orb_x + dx * t_end,
            orb_y + dy * t_end,
        );
        painter.line_segment([start, end], Stroke::new(1.5_f32, beam_color));
    }
}

fn draw_radar_view(ui: &mut egui::Ui, state: &mut EditorState, width: f32, height: f32) {
    let (rect, response) = ui.allocate_at_least(Vec2::new(width, height), egui::Sense::click_and_drag());

    if ui.is_rect_visible(rect) {
        let painter = ui.painter();
        let bg = Color32::from_rgba_premultiplied(8, 8, 20, 240);
        painter.rect_filled(rect, 4.0, bg);

        let center = rect.center();
        let radar_radius = width * 0.4;

        let ring_color = Color32::from_rgba_premultiplied(15, 240, 252, 30);
        for i in 1..=4 {
            let r = radar_radius * (i as f32 / 4.0);
            painter.circle_stroke(center, r, Stroke::new(0.5_f32, ring_color));
        }

        let cross_color = Color32::from_rgba_premultiplied(15, 240, 252, 20);
        painter.line_segment(
            [pos2(center.x - radar_radius, center.y), pos2(center.x + radar_radius, center.y)],
            Stroke::new(0.5_f32, cross_color),
        );
        painter.line_segment(
            [pos2(center.x, center.y - radar_radius), pos2(center.x, center.y + radar_radius)],
            Stroke::new(0.5_f32, cross_color),
        );

        let az_rad = state.gui.params.position.azimuth.to_radians();
        let dist_norm = (state.gui.params.position.distance - 0.3) / (3.0 - 0.3);
        let log_dist = (dist_norm.ln() / 3.0_f32.ln()).clamp(0.0, 1.0);
        let dot_dist = log_dist * radar_radius;

        let dot_x = center.x + dot_dist * az_rad.sin();
        let dot_y = center.y - dot_dist * az_rad.cos();

        painter.circle_filled(pos2(dot_x, dot_y), 4.0, CORAL);
        painter.circle_filled(
            pos2(dot_x, dot_y),
            6.0,
            Color32::from_rgba_premultiplied(255, 107, 53, 40),
        );

        painter.text(
            pos2(center.x, rect.max.y - 2.0),
            egui::Align2::CENTER_BOTTOM,
            format!("{}°", state.gui.params.position.azimuth as i32),
            egui::FontId::proportional(8.0),
            TEXT_DIM,
        );
    }

    if response.dragged() {
        let mouse_pos = response.interact_pointer_pos().unwrap();
        let center = rect.center();
        let radar_radius = width * 0.4;

        let dx = (mouse_pos.x - center.x) / radar_radius;
        let dy = -(mouse_pos.y - center.y) / radar_radius;

        let az = dx.atan2(dy).to_degrees();
        state.gui.params.position.azimuth = az.clamp(-90.0, 90.0);

        let dist_sqrt = (dx * dx + dy * dy).sqrt().clamp(0.0, 1.0);
        let dist_norm = 3.0_f32.powf(dist_sqrt * 3.0_f32.ln());
        state.gui.params.position.distance = 0.3 + dist_norm * (3.0 - 0.3);
    }
}

fn draw_elevation_view(ui: &mut egui::Ui, state: &mut EditorState, width: f32, height: f32) {
    let (rect, response) = ui.allocate_at_least(Vec2::new(width, height), egui::Sense::click_and_drag());

    if ui.is_rect_visible(rect) {
        let painter = ui.painter();
        let bg = Color32::from_rgba_premultiplied(8, 8, 20, 240);
        painter.rect_filled(rect, 4.0, bg);

        let center_x = rect.center().x;
        let head_top = rect.min.y + 15.0;
        let head_bottom = rect.max.y - 15.0;
        let head_center_y = (head_top + head_bottom) / 2.0;

        let head_color = Color32::from_rgba_premultiplied(15, 240, 252, 40);
        painter.text(
            pos2(center_x, head_top - 2.0),
            egui::Align2::CENTER_BOTTOM,
            "+90°",
            egui::FontId::proportional(7.0),
            TEXT_DIM,
        );
        painter.text(
            pos2(center_x, head_bottom + 2.0),
            egui::Align2::CENTER_TOP,
            "-45°",
            egui::FontId::proportional(7.0),
            TEXT_DIM,
        );

        let head_width = 14.0;
        let head_height = 30.0;
        let head_rect = Rect::from_center_size(
            pos2(center_x, head_center_y),
            Vec2::new(head_width, head_height),
        );
        painter.rect_filled(head_rect, 8.0, head_color);
        painter.rect_stroke(
            head_rect,
            8.0,
            Stroke::new(1.0_f32, Color32::from_rgba_premultiplied(15, 240, 252, 60)),
            egui::StrokeKind::Middle,
        );

        let ear_rect = Rect::from_center_size(
            pos2(center_x + head_width * 0.5, head_center_y),
            Vec2::new(4.0, 8.0),
        );
        painter.rect_filled(ear_rect, 2.0, head_color);

        let el_norm = (state.gui.params.position.elevation + 45.0) / 135.0;
        let dot_y = head_bottom - el_norm * (head_bottom - head_top);

        painter.circle_filled(
            pos2(center_x + 25.0, dot_y),
            4.0,
            CORAL,
        );
        painter.circle_filled(
            pos2(center_x + 25.0, dot_y),
            6.0,
            Color32::from_rgba_premultiplied(255, 107, 53, 40),
        );

        let beam_color = Color32::from_rgba_premultiplied(255, 107, 53, 60);
        painter.line_segment(
            [pos2(center_x + 25.0, dot_y), pos2(center_x + head_width * 0.5, head_center_y)],
            Stroke::new(1.0_f32, beam_color),
        );

        painter.text(
            pos2(center_x + 35.0, dot_y),
            egui::Align2::LEFT_CENTER,
            format!("{}°", state.gui.params.position.elevation as i32),
            egui::FontId::proportional(8.0),
            TEXT_DIM,
        );
    }

    if response.dragged() {
        let mouse_pos = response.interact_pointer_pos().unwrap();
        let head_top = rect.min.y + 15.0;
        let head_bottom = rect.max.y - 15.0;

        let norm = 1.0 - ((mouse_pos.y - head_top) / (head_bottom - head_top)).clamp(0.0, 1.0);
        state.gui.params.position.elevation = -45.0 + norm * 135.0;
    }
}

fn draw_knobs_column(ui: &mut egui::Ui, state: &mut EditorState) {
    ui.vertical(|ui| {
        ui.label(RichText::new("AZIMUTH").color(TEXT_DIM).size(9.0));
        let az_knob = knob::NeonKnob::new(
            "",
            state.gui.params.position.azimuth,
            -90.0,
            90.0,
            "°",
            TEAL,
        )
        .with_size(56.0);
        let az_resp = ui.add(az_knob);
        if az_resp.dragged() {
            let delta = az_resp.drag_delta().x * 0.5;
            state.gui.params.position.azimuth = (state.gui.params.position.azimuth + delta).clamp(-90.0, 90.0);
        }

        ui.add_space(8.0);

        ui.label(RichText::new("ELEVATION").color(TEXT_DIM).size(9.0));
        let el_knob = knob::NeonKnob::new(
            "",
            state.gui.params.position.elevation,
            -45.0,
            90.0,
            "°",
            TEAL,
        )
        .with_size(56.0);
        let el_resp = ui.add(el_knob);
        if el_resp.dragged() {
            let delta = el_resp.drag_delta().y * -0.5;
            state.gui.params.position.elevation = (state.gui.params.position.elevation + delta).clamp(-45.0, 90.0);
        }

        ui.add_space(8.0);

        ui.label(RichText::new("ROOM").color(TEXT_DIM).size(9.0));
        let room_knob = knob::NeonKnob::new(
            "",
            state.gui.params.room_amount,
            0.0,
            1.0,
            "%",
            VIOLET,
        )
        .with_size(56.0);
        let room_resp = ui.add(room_knob);
        if room_resp.dragged() {
            let delta = room_resp.drag_delta().x * 0.005;
            state.gui.params.room_amount = (state.gui.params.room_amount + delta).clamp(0.0, 1.0);
        }

        ui.add_space(8.0);

        ui.label(RichText::new("DRY/WET").color(TEXT_DIM).size(9.0));
        let mix_knob = knob::NeonKnob::new(
            "",
            state.gui.params.mix,
            0.0,
            1.0,
            "%",
            CORAL,
        )
        .with_size(56.0);
        let mix_resp = ui.add(mix_knob);
        if mix_resp.dragged() {
            let delta = mix_resp.drag_delta().x * 0.005;
            state.gui.params.mix = (state.gui.params.mix + delta).clamp(0.0, 1.0);
        }

        ui.add_space(12.0);

        draw_room_segmented(ui, state);
        ui.add_space(8.0);
        draw_mono_maker_led(ui, state);
    });
}

fn draw_room_segmented(ui: &mut egui::Ui, state: &mut EditorState) {
    ui.label(RichText::new("ROOM MODEL").color(TEXT_DIM).size(9.0));

    ui.horizontal(|ui| {
        for (i, model) in RoomModel::all().iter().enumerate() {
            let is_active = state.gui.params.room as usize == i;
            let bg = if is_active {
                Color32::from_rgba_premultiplied(124, 58, 237, 180)
            } else {
                Color32::from_rgba_premultiplied(30, 30, 50, 200)
            };
            let text_color = if is_active { TEXT_BRIGHT } else { TEXT_DIM };

            let btn = egui::Button::new(
                RichText::new(model.label()).color(text_color).size(9.0),
            )
            .fill(bg)
            .stroke(Stroke::new(
                1.0_f32,
                if is_active {
                    VIOLET
                } else {
                    Color32::from_rgba_premultiplied(60, 60, 80, 100)
                },
            ));

            if ui.add(btn).clicked() {
                state.gui.params.room = *model;
            }
        }
    });
}

fn draw_mono_maker_led(ui: &mut egui::Ui, state: &mut EditorState) {
    ui.horizontal(|ui| {
        let led_color = if state.gui.params.bass_mono {
            TEAL
        } else {
            Color32::from_rgba_premultiplied(60, 60, 80, 100)
        };

        let (led_rect, led_resp) =
            ui.allocate_at_least(Vec2::new(16.0, 16.0), egui::Sense::click());

        if ui.is_rect_visible(led_rect) {
            let painter = ui.painter();
            painter.circle_filled(led_rect.center(), 6.0, led_color);
            if state.gui.params.bass_mono {
                painter.circle_filled(
                    led_rect.center(),
                    8.0,
                    Color32::from_rgba_premultiplied(15, 240, 252, 40),
                );
            }
        }

        if led_resp.clicked() {
            state.gui.params.bass_mono = !state.gui.params.bass_mono;
        }

        ui.label(
            RichText::new("MONO-MAKER")
                .color(TEXT_DIM)
                .size(9.0),
        );
    });
}

fn draw_preset_bar(ui: &mut egui::Ui, state: &mut EditorState) {
    ui.add_space(4.0);
    ui.separator();
    ui.add_space(4.0);

    ui.horizontal(|ui| {
        ui.add_space(8.0);

        ui.label(RichText::new("PRESET:").color(TEXT_DIM).size(10.0));

        for (i, preset) in PRESETS.iter().enumerate() {
            let is_active = state.gui.preset_index == i;
            let bg = if is_active {
                egui::Color32::from_rgba_premultiplied(255, 107, 53, 180)
            } else {
                egui::Color32::from_rgba_premultiplied(30, 30, 50, 200)
            };
            let text_color = if is_active { TEXT_BRIGHT } else { TEXT_DIM };

            let btn = egui::Button::new(
                RichText::new(preset.name).color(text_color).size(10.0),
            )
            .fill(bg)
            .stroke(Stroke::new(
                1.0_f32,
                if is_active {
                    CORAL
                } else {
                    Color32::from_rgba_premultiplied(60, 60, 80, 100)
                },
            ));

            if ui.add(btn).clicked() {
                state.gui.load_preset(i);
            }
        }
    });
}
