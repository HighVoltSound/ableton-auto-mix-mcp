use std::f32::consts::PI;

pub struct SpatializerDsp {
    sample_rate: f32,
    delay_buffer_l: [f32; 256],
    delay_buffer_r: [f32; 256],
    write_pos: usize,

    shadow_state_l: [f32; 2],
    shadow_state_r: [f32; 2],
    notch_state_l: [f32; 2],
    notch_state_r: [f32; 2],

    // Для Smart Depth (Air Absorption)
    hf_damp_l: f32,
    hf_damp_r: f32,

    // Для Split Spatial (Mid/Side processing)
    side_hp_state: f32,
    side_high_shelf: f32,

    room_buffer: Vec<f32>,
    room_write_pos: usize,
    room_lp_l: f32,
    room_lp_r: f32,
}

impl SpatializerDsp {
    pub fn new(sample_rate: f32) -> Self {
        let max_room_samples = (sample_rate * 0.3) as usize + 256;
        Self {
            sample_rate,
            delay_buffer_l: [0.0; 256],
            delay_buffer_r: [0.0; 256],
            write_pos: 0,
            shadow_state_l: [0.0; 2],
            shadow_state_r: [0.0; 2],
            notch_state_l: [0.0; 2],
            notch_state_r: [0.0; 2],
            hf_damp_l: 0.0,
            hf_damp_r: 0.0,
            side_hp_state: 0.0,
            side_high_shelf: 0.0,
            room_buffer: vec![0.0; max_room_samples],
            room_write_pos: 0,
            room_lp_l: 0.0,
            room_lp_r: 0.0,
        }
    }

    pub fn set_sample_rate(&mut self, sample_rate: f32) {
        self.sample_rate = sample_rate;
        let max_room_samples = (sample_rate * 0.3) as usize + 256;
        self.room_buffer = vec![0.0; max_room_samples];
        self.reset();
    }

    pub fn reset(&mut self) {
        self.delay_buffer_l.fill(0.0);
        self.delay_buffer_r.fill(0.0);
        self.write_pos = 0;
        self.shadow_state_l = [0.0; 2];
        self.shadow_state_r = [0.0; 2];
        self.notch_state_l = [0.0; 2];
        self.notch_state_r = [0.0; 2];
        self.hf_damp_l = 0.0;
        self.hf_damp_r = 0.0;
        self.side_hp_state = 0.0;
        self.side_high_shelf = 0.0;
        self.room_buffer.fill(0.0);
        self.room_write_pos = 0;
        self.room_lp_l = 0.0;
        self.room_lp_r = 0.0;
    }

    #[allow(clippy::too_many_arguments)]
    pub fn process_frame(
        &mut self,
        in_l: f32,
        in_r: f32,
        head_pos: f32,
        azimuth_deg: f32,
        elevation_deg: f32,
        distance_m: f32,
        split_spatial: i32, // 0 = Off, 1 = Mid, 2 = Wide
        club_safe: bool,
        room_model: i32,
        room_amount: f32,
        mix: f32,
    ) -> (f32, f32) {
        let mono_in = (in_l + in_r) * 0.5;

        // 1. ITD Calculation
        let r_head = 0.0875;
        let c_sound = 343.0;
        let theta_rad = (azimuth_deg.clamp(-90.0, 90.0) * PI) / 180.0;
        let elev_clamped = elevation_deg.clamp(-45.0, 90.0);
        let elev_factor = if club_safe {
            1.0 // Disable elevation delay manipulation for phase safety
        } else {
            (elev_clamped.max(0.0) * PI / 180.0).cos().max(0.0)
        };

        let mut itd_sec = (r_head / c_sound) * (theta_rad.abs() + theta_rad.abs().sin()) * elev_factor;
        
        // Club Safe Mode limits ITD delay to prevent severe comb filtering when summed to mono
        if club_safe {
            itd_sec *= 0.6;
        }

        let itd_samples = itd_sec * self.sample_rate;

        let (delay_l, delay_r) = if azimuth_deg > 0.0 {
            (itd_samples, 0.0)
        } else {
            (0.0, itd_samples)
        };

        self.delay_buffer_l[self.write_pos] = mono_in;
        self.delay_buffer_r[self.write_pos] = mono_in;

        let mut out_l = self.read_delay_l(delay_l);
        let mut out_r = self.read_delay_r(delay_r);

        self.write_pos = (self.write_pos + 1) % 256;

        // 2. ILD Head Shadowing
        let shadow_amount = theta_rad.abs().sin() * elev_factor;
        if shadow_amount > 0.05 {
            let cutoff = (4500.0 - shadow_amount * 2500.0).max(800.0);
            let alpha = (2.0 * PI * cutoff / self.sample_rate).min(0.85);
            let safe_shadow = if club_safe { shadow_amount * 0.5 } else { shadow_amount };

            if azimuth_deg > 0.0 {
                self.shadow_state_l[0] += alpha * (out_l - self.shadow_state_l[0]);
                out_l = (1.0 - safe_shadow * 0.5) * out_l + (safe_shadow * 0.5) * self.shadow_state_l[0];
                out_l *= 1.0 - safe_shadow * 0.35;
            } else {
                self.shadow_state_r[0] += alpha * (out_r - self.shadow_state_r[0]);
                out_r = (1.0 - safe_shadow * 0.5) * out_r + (safe_shadow * 0.5) * self.shadow_state_r[0];
                out_r *= 1.0 - safe_shadow * 0.35;
            }
        }

        // 3. HRTF Pinna/Occiput Filters (Disabled in Club Safe for phase integrity)
        if !club_safe {
            let pos = head_pos.clamp(0.0, 1.0);
            if pos < 0.40 {
                let back_factor = (0.40 - pos) / 0.40;
                let notch_freq = 7200.0 - back_factor * 1200.0;
                let w0 = 2.0 * PI * notch_freq / self.sample_rate;
                let alpha_notch = w0.sin() / 6.0;
                let a0 = 1.0 + alpha_notch;
                
                let notch_l = (out_l + self.notch_state_l[1] - 2.0 * w0.cos() * self.notch_state_l[0]) / a0;
                self.notch_state_l[1] = self.notch_state_l[0];
                self.notch_state_l[0] = out_l - (-2.0 * w0.cos() / a0) * self.notch_state_l[0] - ((1.0 - alpha_notch) / a0) * self.notch_state_l[1];

                let notch_r = (out_r + self.notch_state_r[1] - 2.0 * w0.cos() * self.notch_state_r[0]) / a0;
                self.notch_state_r[1] = self.notch_state_r[0];
                self.notch_state_r[0] = out_r - (-2.0 * w0.cos() / a0) * self.notch_state_r[0] - ((1.0 - alpha_notch) / a0) * self.notch_state_r[1];

                out_l = (1.0 - back_factor * 0.55) * out_l + (back_factor * 0.55) * notch_l;
                out_r = (1.0 - back_factor * 0.55) * out_r + (back_factor * 0.55) * notch_r;
            }

            // Elevation (Zenith Air)
            if elev_clamped > 5.0 {
                let air_gain = 1.0 + (elev_clamped / 90.0).min(1.0) * 0.25;
                out_l *= air_gain;
                out_r *= air_gain;
            }
        }

        // 4. SMART DEPTH (Distance attenuation + HF Air Absorption + DRR mapping)
        let dist = distance_m.max(0.3);
        let dist_gain = 1.0 / dist.sqrt();
        
        // HF Rolloff based on distance (Air absorption)
        let hf_cutoff = (20000.0 - (dist - 0.3) * 6000.0).clamp(2000.0, 20000.0);
        let hf_alpha = (2.0 * PI * hf_cutoff / self.sample_rate).min(1.0);
        
        self.hf_damp_l += hf_alpha * (out_l - self.hf_damp_l);
        self.hf_damp_r += hf_alpha * (out_r - self.hf_damp_r);
        
        out_l = self.hf_damp_l * dist_gain;
        out_r = self.hf_damp_r * dist_gain;

        // 5. Room Early Reflections (Scales with Distance / Smart Depth)
        // Direct/Reverberant Ratio: close = dry, far = wet
        let auto_room_amount = room_amount * (0.2 + (dist - 0.3) / 2.7 * 0.8);
        
        if room_model > 0 && auto_room_amount > 0.01 && !self.room_buffer.is_empty() {
            let buf_len = self.room_buffer.len();
            self.room_buffer[self.room_write_pos] = mono_in;

            let (refl_l, refl_r) = match room_model {
                1 => { // Booth
                    let d1 = self.read_room(8.0) * 0.25;
                    let d2 = self.read_room(14.0) * 0.18;
                    (d1 - d2 * 0.5, d1 + d2 * 0.5)
                }
                2 => { // Studio
                    let d1 = self.read_room(18.0) * 0.35;
                    let d2 = self.read_room(28.0) * 0.25;
                    (d1 - d2 * 0.6, d1 + d2 * 0.6)
                }
                3 => { // Club
                    let d1 = self.read_room(35.0) * 0.45;
                    let d2 = self.read_room(65.0) * 0.35;
                    (d1 - d2 * 0.7, d1 + d2 * 0.7)
                }
                _ => { // Cathedral
                    let d1 = self.read_room(60.0) * 0.50;
                    let d2 = self.read_room(110.0) * 0.42;
                    (d1 - d2 * 0.8, d1 + d2 * 0.8)
                }
            };

            let lp_alpha = (2.0 * PI * 4500.0 / self.sample_rate).min(0.6);
            self.room_lp_l += lp_alpha * (refl_l - self.room_lp_l);
            self.room_lp_r += lp_alpha * (refl_r - self.room_lp_r);

            out_l += self.room_lp_l * auto_room_amount;
            out_r += self.room_lp_r * auto_room_amount;
            
            self.room_write_pos = (self.room_write_pos + 1) % buf_len;
        }

        // 6. SPLIT SPATIAL (Mid/Side processing)
        // Splits the signal to ensure Mono-bass and Wide-highs
        if split_spatial > 0 {
            let mid = (out_l + out_r) * 0.5;
            let mut side = (out_l - out_r) * 0.5;

            // HPF on Side at 120Hz (Mono-Maker)
            let side_hp_alpha = (2.0 * PI * 120.0 / self.sample_rate).min(0.2);
            self.side_hp_state += side_hp_alpha * (side - self.side_hp_state);
            side -= self.side_hp_state; // Remove sub from side

            // High Shelf on Side at 4kHz (Widener)
            if split_spatial == 2 { // Wide mode
                let shelf_alpha = (2.0 * PI * 4000.0 / self.sample_rate).min(0.5);
                self.side_high_shelf += shelf_alpha * (side - self.side_high_shelf);
                let side_highs = side - self.side_high_shelf;
                side += side_highs * 0.5; // Boost side highs by 50%
            }

            out_l = mid + side;
            out_r = mid - side;
        }

        let wet_l = (1.0 - mix) * in_l + mix * out_l;
        let wet_r = (1.0 - mix) * in_r + mix * out_r;

        (wet_l, wet_r)
    }

    fn read_delay_l(&self, delay_samples: f32) -> f32 {
        let int_d = delay_samples.floor() as usize;
        let frac_d = delay_samples - (int_d as f32);
        let idx1 = (self.write_pos + 256 - int_d) % 256;
        let idx2 = (self.write_pos + 256 - int_d - 1) % 256;
        (1.0 - frac_d) * self.delay_buffer_l[idx1] + frac_d * self.delay_buffer_l[idx2]
    }

    fn read_delay_r(&self, delay_samples: f32) -> f32 {
        let int_d = delay_samples.floor() as usize;
        let frac_d = delay_samples - (int_d as f32);
        let idx1 = (self.write_pos + 256 - int_d) % 256;
        let idx2 = (self.write_pos + 256 - int_d - 1) % 256;
        (1.0 - frac_d) * self.delay_buffer_r[idx1] + frac_d * self.delay_buffer_r[idx2]
    }

    fn read_room(&self, delay_ms: f32) -> f32 {
        let samples = (delay_ms / 1000.0) * self.sample_rate;
        let buf_len = self.room_buffer.len();
        let int_d = samples.floor() as usize;
        let frac_d = samples - (int_d as f32);
        let idx1 = (self.room_write_pos + buf_len - (int_d % buf_len)) % buf_len;
        let idx2 = (self.room_write_pos + buf_len - ((int_d + 1) % buf_len)) % buf_len;
        (1.0 - frac_d) * self.room_buffer[idx1] + frac_d * self.room_buffer[idx2]
    }
}
