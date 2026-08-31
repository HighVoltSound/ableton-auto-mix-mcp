use std::f32::consts::PI;

pub struct Camera {
    pub yaw: f32,
    pub pitch: f32,
    pub distance: f32,
    pub target: [f32; 3],
}

impl Camera {
    pub fn new() -> Self {
        Self {
            yaw: PI * 0.25,
            pitch: PI * 0.15,
            distance: 4.0,
            target: [0.0, 0.0, 0.0],
        }
    }

    pub fn orbit(&mut self, dx: f32, dy: f32) {
        self.yaw += dx;
        self.pitch = (self.pitch + dy).clamp(-PI * 0.45, PI * 0.45);
    }

    pub fn position(&self) -> [f32; 3] {
        let x = self.distance * self.pitch.cos() * self.yaw.sin();
        let y = self.distance * self.pitch.sin();
        let z = self.distance * self.pitch.cos() * self.yaw.cos();
        [
            x + self.target[0],
            y + self.target[1],
            z + self.target[2],
        ]
    }

    pub fn view_matrix(&self) -> [[f32; 4]; 4] {
        let eye = self.position();
        let center = self.target;
        let up = [0.0f32, 1.0, 0.0];

        let f = normalize(sub(center, eye));
        let s = normalize(cross(f, up));
        let u = cross(s, f);

        [
            [s[0], u[0], -f[0], 0.0],
            [s[1], u[1], -f[1], 0.0],
            [s[2], u[2], -f[2], 0.0],
            [-dot(s, eye), -dot(u, eye), dot(f, eye), 1.0],
        ]
    }

    pub fn projection_matrix(&self, aspect: f32) -> [[f32; 4]; 4] {
        let fov = PI / 4.0;
        let near = 0.1;
        let far = 100.0;

        let f = 1.0 / (fov / 2.0).tan();
        let nf = 1.0 / (near - far);

        [
            [f / aspect, 0.0, 0.0, 0.0],
            [0.0, f, 0.0, 0.0],
            [0.0, 0.0, (far + near) * nf, -1.0],
            [0.0, 0.0, 2.0 * far * near * nf, 0.0],
        ]
    }

    pub fn view_projection_matrix(&self, aspect: f32) -> [[f32; 4]; 4] {
        let view = self.view_matrix();
        let proj = self.projection_matrix(aspect);
        mul_mat4(proj, view)
    }
}

impl Default for Camera {
    fn default() -> Self {
        Self::new()
    }
}

fn sub(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
}

fn cross(a: [f32; 3], b: [f32; 3]) -> [f32; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

fn dot(a: [f32; 3], b: [f32; 3]) -> f32 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

fn normalize(v: [f32; 3]) -> [f32; 3] {
    let len = dot(v, v).sqrt();
    if len < 1e-8 {
        return [0.0; 3];
    }
    [v[0] / len, v[1] / len, v[2] / len]
}

fn mul_mat4(a: [[f32; 4]; 4], b: [[f32; 4]; 4]) -> [[f32; 4]; 4] {
    let mut result = [[0.0f32; 4]; 4];
    for i in 0..4 {
        for j in 0..4 {
            result[i][j] = a[i][0] * b[0][j]
                + a[i][1] * b[1][j]
                + a[i][2] * b[2][j]
                + a[i][3] * b[3][j];
        }
    }
    result
}
