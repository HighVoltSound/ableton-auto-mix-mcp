use nih_plug_egui::egui::{self, pos2, vec2, Color32, Pos2, Rect, Response, Sense, Stroke, Ui, Vec2, Widget};
use std::f32::consts::PI;

pub struct NeonKnob<'a> {
    label: &'a str,
    value: f32,
    min: f32,
    max: f32,
    suffix: &'a str,
    color: Color32,
    size: f32,
}

impl<'a> NeonKnob<'a> {
    pub fn new(
        label: &'a str,
        value: f32,
        min: f32,
        max: f32,
        suffix: &'a str,
        color: Color32,
    ) -> Self {
        Self {
            label,
            value,
            min,
            max,
            suffix,
            color,
            size: 60.0,
        }
    }

    pub fn with_size(mut self, size: f32) -> Self {
        self.size = size;
        self
    }

    fn normalized(&self) -> f32 {
        (self.value - self.min) / (self.max - self.min)
    }

    fn angle(&self) -> f32 {
        let norm = self.normalized();
        PI * 0.75 + norm * PI * 1.5
    }

    fn knob_center(&self, rect: Rect) -> Pos2 {
        rect.center()
    }

    fn draw_background(&self, painter: &egui::Painter, center: Pos2, radius: f32) {
        let bg_color = Color32::from_rgba_premultiplied(20, 20, 40, 200);
        painter.circle_filled(center, radius, bg_color);

        let border_color = Color32::from_rgba_premultiplied(80, 80, 120, 150);
        painter.circle_stroke(center, radius, Stroke::new(1.0_f32, border_color));
    }

    fn draw_ring(&self, painter: &egui::Painter, center: Pos2, radius: f32) {
        let ring_radius = radius + 3.0;
        let start_angle = PI * 0.75;
        let end_angle = PI * 2.25;

        let segments = 64;
        let mut points = Vec::with_capacity(segments + 1);

        for i in 0..=segments {
            let t = i as f32 / segments as f32;
            let angle = start_angle + t * (end_angle - start_angle);
            let x = center.x + ring_radius * angle.cos();
            let y = center.y + ring_radius * angle.sin();
            points.push(pos2(x, y));
        }

        let track_color = Color32::from_rgba_premultiplied(60, 60, 80, 100);
        for window in points.windows(2) {
            painter.line_segment(
                [window[0], window[1]],
                Stroke::new(2.0_f32, track_color),
            );
        }

        let value_angle = self.angle();
        let value_norm = self.normalized();
        let filled_segments = (value_norm * segments as f32) as usize;

        let mut filled_points = Vec::with_capacity(filled_segments + 1);
        for i in 0..=filled_segments.min(segments) {
            let t = i as f32 / segments as f32;
            let angle = start_angle + t * (end_angle - start_angle);
            let x = center.x + ring_radius * angle.cos();
            let y = center.y + ring_radius * angle.sin();
            filled_points.push(pos2(x, y));
        }

        for window in filled_points.windows(2) {
            painter.line_segment([window[0], window[1]], Stroke::new(3.0_f32, self.color));
        }

        let indicator_x = center.x + ring_radius * value_angle.cos();
        let indicator_y = center.y + ring_radius * value_angle.sin();
        painter.circle_filled(
            pos2(indicator_x, indicator_y),
            4.0,
            self.color,
        );
    }

    fn draw_indicator(&self, painter: &egui::Painter, center: Pos2, radius: f32) {
        let angle = self.angle();
        let inner_radius = radius * 0.3;
        let outer_radius = radius * 0.7;

        let start = pos2(
            center.x + inner_radius * angle.cos(),
            center.y + inner_radius * angle.sin(),
        );
        let end = pos2(
            center.x + outer_radius * angle.cos(),
            center.y + outer_radius * angle.sin(),
        );

        painter.line_segment([start, end], Stroke::new(2.0_f32, self.color));
    }

    fn draw_label(&self, painter: &egui::Painter, rect: Rect) {
        let text_pos = pos2(rect.center().x, rect.max.y + 14.0);
        painter.text(
            text_pos,
            egui::Align2::CENTER_CENTER,
            self.label,
            egui::FontId::proportional(11.0),
            Color32::from_rgba_premultiplied(200, 200, 220, 200),
        );
    }

    fn draw_value(&self, painter: &egui::Painter, center: Pos2) {
        let text = format!("{:.1}{}", self.value, self.suffix);
        painter.text(
            pos2(center.x, center.y + 8.0),
            egui::Align2::CENTER_CENTER,
            text,
            egui::FontId::proportional(10.0),
            Color32::from_rgba_premultiplied(180, 180, 200, 180),
        );
    }
}

impl Widget for NeonKnob<'_> {
    fn ui(self, ui: &mut Ui) -> Response {
        let size = vec2(self.size, self.size + 30.0);
        let (rect, response) = ui.allocate_at_least(size, Sense::click_and_drag());

        let knob_rect = Rect::from_center_size(
            rect.center() - vec2(0.0, 15.0),
            vec2(self.size, self.size),
        );

        let center = knob_rect.center();
        let radius = self.size * 0.35;

        if ui.is_rect_visible(rect) {
            let painter = ui.painter();

            self.draw_background(painter, center, radius);
            self.draw_ring(painter, center, radius);
            self.draw_indicator(painter, center, radius);
            self.draw_value(painter, center);
            self.draw_label(painter, knob_rect);
        }

        response
    }
}
