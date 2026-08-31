use nih_plug_egui::egui::{Pos2, Color32, Stroke, Painter};

pub struct Vec3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

impl Vec3 {
    pub fn new(x: f32, y: f32, z: f32) -> Self {
        Self { x, y, z }
    }

    // Вращение вокруг оси Y (Azimuth)
    pub fn rotate_y(self, angle_rad: f32) -> Self {
        let (sin, cos) = angle_rad.sin_cos();
        Self {
            x: self.x * cos + self.z * sin,
            y: self.y,
            z: -self.x * sin + self.z * cos,
        }
    }

    // Вращение вокруг оси X (Elevation)
    pub fn rotate_x(self, angle_rad: f32) -> Self {
        let (sin, cos) = angle_rad.sin_cos();
        Self {
            x: self.x,
            y: self.y * cos - self.z * sin,
            z: self.y * sin + self.z * cos,
        }
    }
}

pub fn draw_hologram(
    painter: &Painter,
    center: Pos2,
    scale: f32,
    azimuth_deg: f32,
    elevation_deg: f32,
    distance: f32,
) {
    let az = azimuth_deg.to_radians();
    let el = elevation_deg.to_radians();

    let color_dim = Color32::from_rgba_premultiplied(0, 150, 255, 30);
    let color_bright = Color32::from_rgba_premultiplied(0, 255, 255, 120);

    // Функция проецирования 3D в 2D (ортографическая + перспектива)
    let project = |v: Vec3| -> Pos2 {
        let rotated = v.rotate_x(-el).rotate_y(az);
        // Добавляем эффект перспективы (чем дальше Z, тем меньше масштаб)
        let z_factor = 3.0 / (3.0 - rotated.z.clamp(-1.5, 1.5) * 0.5);
        Pos2::new(
            center.x + rotated.x * scale * z_factor,
            center.y - rotated.y * scale * z_factor, // Y инвертирован в UI
        )
    };

    // 1. Рисуем сферу (голову) - набор горизонтальных и вертикальных колец
    let draw_ring = |is_horizontal: bool, offset: f32, radius: f32, steps: usize| {
        let mut points = Vec::new();
        for i in 0..=steps {
            let angle = (i as f32 / steps as f32) * std::f32::consts::PI * 2.0;
            let (sin, cos) = angle.sin_cos();
            
            let v = if is_horizontal {
                Vec3::new(cos * radius, offset, sin * radius)
            } else {
                Vec3::new(cos * radius, sin * radius, offset) // Вертикальное
            };
            points.push(project(v));
        }
        for i in 0..steps {
            painter.line_segment([points[i], points[i+1]], Stroke::new(1.0_f32, color_dim));
        }
    };

    // Горизонтальные кольца (широты)
    for i in -3..=3 {
        let y = (i as f32) * 0.25;
        let r = (1.0 - y * y).sqrt().max(0.0);
        draw_ring(true, y, r, 32);
    }
    // Вертикальные кольца (долготы)
    for i in 0..4 {
        let angle = (i as f32 / 4.0) * std::f32::consts::PI;
        let mut points = Vec::new();
        for step in 0..=32 {
            let a = (step as f32 / 32.0) * std::f32::consts::PI * 2.0;
            let (sin, cos) = a.sin_cos();
            let v = Vec3::new(cos * angle.cos(), sin, cos * angle.sin());
            points.push(project(v));
        }
        for step in 0..32 {
            painter.line_segment([points[step], points[step+1]], Stroke::new(1.0_f32, color_dim));
        }
    }

    // 2. Рисуем нос (для ориентации головы)
    let nose_base = Vec3::new(0.0, 0.0, 1.0);
    let nose_tip = Vec3::new(0.0, -0.2, 1.3);
    painter.line_segment([project(nose_base), project(nose_tip)], Stroke::new(2.0_f32, color_bright));

    // 3. Рисуем орбиту звукового источника
    let dist_scale = 1.2 + (distance / 3.0) * 1.5; // Расстояние от 1.2 до 2.7 радиусов
    let orbit_radius = dist_scale;
    let mut orbit_points = Vec::new();
    for i in 0..=64 {
        let angle = (i as f32 / 64.0) * std::f32::consts::PI * 2.0;
        let (sin, cos) = angle.sin_cos();
        // Орбита звука (горизонтальная плоскость, наклоненная по Elevation)
        let v = Vec3::new(sin * orbit_radius, 0.0, cos * orbit_radius);
        orbit_points.push(project(v));
    }
    for i in 0..64 {
        painter.line_segment([orbit_points[i], orbit_points[i+1]], Stroke::new(1.5_f32, Color32::from_rgba_premultiplied(255, 107, 53, 50)));
    }

    // 4. Сам звуковой источник (Target)
    let target = Vec3::new(0.0, 0.0, orbit_radius);
    let t_proj = project(target);
    
    // Свечение орба
    painter.circle_filled(t_proj, 15.0, Color32::from_rgba_premultiplied(255, 107, 53, 20));
    painter.circle_filled(t_proj, 8.0, Color32::from_rgba_premultiplied(255, 107, 53, 80));
    painter.circle_filled(t_proj, 4.0, Color32::from_rgba_premultiplied(255, 200, 150, 255));
    
    // Линия от головы к источнику
    painter.line_segment([project(Vec3::new(0.0,0.0,1.0)), t_proj], Stroke::new(1.0_f32, Color32::from_rgba_premultiplied(255, 107, 53, 100)));
}
