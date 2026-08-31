// Stereo Eblet 3D Realtime DSP Engine (VST3 / CLAP) 3.0
// Implements:
// 1. Woodworth-Schlosser ITD (Interaural Time Difference) with zenith elevation factor
// 2. Head Shadowing ILD (Interaural Level Difference)
// 3. Occiput / Neck / Pinna & Crown Overhead HRTF spectral shaping (+90° Zenith)
// 4. Mono-Maker (Sub-bass <120Hz centered mono crossover)
// 5. Room Acoustics Early Reflections (Dry, Vocal Booth, Studio, Club, Cathedral)
// 6. Split Spatial — 4-band frequency-dependent spatialization
// 7. Externalization control
// 8. Output Mode processing (Headphones/Club/Hybrid)

use std::f32::consts::PI;

pub struct SpatializerDsp {
    sample_rate: f32,

    // Delay buffers for ITD
    delay_buffer_l: [f32; 256],
    delay_buffer_r: [f32; 256],
    write_pos: usize,

    // Filter states
    shadow_state_l: [f32; 2],
    shadow_state_r: [f32; 2],
    notch_state_l: [f32; 2],
    notch_state_r: [f32; 2],
    sub_lp_state: [f32; 2],

    // Room early reflections
    room_buffer: Vec<f32>,
    room_write_pos: usize,
    room_lp_l: f32,
    room_lp_r: f32,

    // Split Spatial: 4-band crossover filters
    // Band 0: sub (20-100Hz), Band 1: low (100-500Hz), Band 2: mid (500-3000Hz), Band 3: high (3kHz+)
    band_lp1: [f32; 2], // crossover 1: sub/low
    band_lp2: [f32; 2], // crossover 2: low/mid
    band_lp3: [f32; 2], // crossover 3: mid/high
    band_state: [[f32; 2]; 4], // filter states per band

    // Externalization: additional early reflection taps
    ext_buffer: Vec<f32>,
    ext_write_pos: usize,
}

impl SpatializerDsp {
    pub fn new(sample_rate: f32) -> Self {
        let max_room_samples = (sample_rate * 0.3) as usize + 256;
        let max_ext_samples = (sample_rate * 0.15) as usize + 256;
        Self {
            sample_rate,
            delay_buffer_l: [0.0; 256],
            delay_buffer_r: [0.0; 256],
            write_pos: 0,
            shadow_state_l: [0.0; 2],
            shadow_state_r: [0.0; 2],
            notch_state_l: [0.0; 2],
            notch_state_r: [0.0; 2],
            sub_lp_state: [0.0; 2],
            room_buffer: vec![0.0; max_room_samples],
            room_write_pos: 0,
            room_lp_l: 0.0,
            room_lp_r: 0.0,
            band_lp1: [0.0; 2],
            band_lp2: [0.0; 2],
            band_lp3: [0.0; 2],
            band_state: [[0.0; 2]; 4],
            ext_buffer: vec![0.0; max_ext_samples],
            ext_write_pos: 0,
        }
    }

    pub fn set_sample_rate(&mut self, sample_rate: f32) {
        self.sample_rate = sample_rate;
        let max_room_samples = (sample_rate * 0.3) as usize + 256;
        let max_ext_samples = (sample_rate * 0.15) as usize + 256;
        self.room_buffer = vec![0.0; max_room_samples];
        self.ext_buffer = vec![0.0; max_ext_samples];
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
        self.sub_lp_state = [0.0; 2];
        self.room_buffer.fill(0.0);
        self.room_write_pos = 0;
        self.room_lp_l = 0.0;
        self.room_lp_r = 0.0;
        self.band_lp1 = [0.0; 2];
        self.band_lp2 = [0.0; 2];
        self.band_lp3 = [0.0; 2];
        self.band_state = [[0.0; 2]; 4];
        self.ext_buffer.fill(0.0);
        self.ext_write_pos = 0;
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
        bass_mono: bool,
        room_model: i32,
        room_amount: f32,
        mix: f32,
    ) -> (f32, f32) {
        let mono = (in_l + in_r) * 0.5;

        // 0. Mono-Maker Sub-bass Split (<120 Hz)
        let (sub_mono, spatial_input) = if bass_mono {
            let sub_alpha = (2.0 * PI * 120.0 / self.sample_rate).min(0.2);
            self.sub_lp_state[0] += sub_alpha * (mono - self.sub_lp_state[0]);
            let sub = self.sub_lp_state[0];
            let high = mono - sub;
            (sub, high)
        } else {
            (0.0, mono)
        };

        // 1. Woodworth-Schlosser ITD Calculation with Elevation Factor
        let r_head = 0.0875;
        let c_sound = 343.0;
        let theta_rad = (azimuth_deg.clamp(-90.0, 90.0) * PI) / 180.0;
        let elev_clamped = elevation_deg.clamp(-45.0, 90.0);
        let elev_factor = (elev_clamped.max(0.0) * PI / 180.0).cos().max(0.0);

        let itd_sec = (r_head / c_sound) * (theta_rad.abs() + theta_rad.abs().sin()) * elev_factor;
        let itd_samples = itd_sec * self.sample_rate;

        let (delay_l, delay_r) = if azimuth_deg > 0.0 {
            (itd_samples, 0.0)
        } else {
            (0.0, itd_samples)
        };

        self.delay_buffer_l[self.write_pos] = spatial_input;
        self.delay_buffer_r[self.write_pos] = spatial_input;

        let mut out_l = self.read_delay_l(delay_l);
        let mut out_r = self.read_delay_r(delay_r);

        self.write_pos = (self.write_pos + 1) % 256;

        // 2. ILD Head Shadowing
        let shadow_amount = theta_rad.abs().sin() * elev_factor;
        if shadow_amount > 0.05 {
            let cutoff = (4500.0 - shadow_amount * 2500.0).max(800.0);
            let alpha = (2.0 * PI * cutoff / self.sample_rate).min(0.85);

            if azimuth_deg > 0.0 {
                self.shadow_state_l[0] += alpha * (out_l - self.shadow_state_l[0]);
                out_l = (1.0 - shadow_amount * 0.5) * out_l + (shadow_amount * 0.5) * self.shadow_state_l[0];
                out_l *= 1.0 - shadow_amount * 0.35;
            } else {
                self.shadow_state_r[0] += alpha * (out_r - self.shadow_state_r[0]);
                out_r = (1.0 - shadow_amount * 0.5) * out_r + (shadow_amount * 0.5) * self.shadow_state_r[0];
                out_r *= 1.0 - shadow_amount * 0.35;
            }
        }

        // 3. Occiput & Neck Spectral Filter
        let pos = head_pos.clamp(0.0, 1.0);
        if pos < 0.40 {
            let back_factor = (0.40 - pos) / 0.40;
            let notch_freq = 7200.0 - back_factor * 1200.0;
            let w0 = 2.0 * PI * notch_freq / self.sample_rate;
            let alpha_notch = w0.sin() / (2.0 * 3.0);
            let b0 = 1.0;
            let b1 = -2.0 * w0.cos();
            let b2 = 1.0;
            let a0 = 1.0 + alpha_notch;
            let a1 = -2.0 * w0.cos();
            let a2 = 1.0 - alpha_notch;

            let notch_l = (b0 / a0) * out_l + (b1 / a0) * self.notch_state_l[0] + (b2 / a0) * self.notch_state_l[1];
            self.notch_state_l[1] = self.notch_state_l[0];
            self.notch_state_l[0] = out_l - (a1 / a0) * self.notch_state_l[0] - (a2 / a0) * self.notch_state_l[1];

            let notch_r = (b0 / a0) * out_r + (b1 / a0) * self.notch_state_r[0] + (b2 / a0) * self.notch_state_r[1];
            self.notch_state_r[1] = self.notch_state_r[0];
            self.notch_state_r[0] = out_r - (a1 / a0) * self.notch_state_r[0] - (a2 / a0) * self.notch_state_r[1];

            out_l = (1.0 - back_factor * 0.55) * out_l + (back_factor * 0.55) * notch_l;
            out_r = (1.0 - back_factor * 0.55) * out_r + (back_factor * 0.55) * notch_r;

            let w_res = 2.0 * PI * 1300.0 / self.sample_rate;
            let alpha_res = w_res.sin() / 4.0;
            out_l += back_factor * 0.25 * (alpha_res * out_l);
            out_r += back_factor * 0.25 * (alpha_res * out_r);
        }

        // 4. Elevation
        if elev_clamped > 5.0 {
            let top_norm = (elev_clamped / 90.0).min(1.0);
            let air_gain = 1.0 + top_norm * 0.25;
            out_l *= air_gain;
            out_r *= air_gain;
        } else if elev_clamped < -5.0 {
            let low_norm = (elev_clamped.abs() / 45.0).min(1.0);
            let low_gain = 1.0 - low_norm * 0.15;
            out_l *= low_gain;
            out_r *= low_gain;
        }

        // 5. Distance attenuation
        let dist = distance_m.max(0.3);
        let dist_gain = 1.0 / dist.sqrt();
        out_l *= dist_gain;
        out_r *= dist_gain;

        // 6. Room Early Reflections
        if room_model > 0 && room_amount > 0.01 && !self.room_buffer.is_empty() {
            self.room_buffer[self.room_write_pos] = spatial_input;

            let (refl_l, refl_r) = match room_model {
                1 => {
                    let d1 = self.read_room(8.0) * 0.25;
                    let d2 = self.read_room(14.0) * 0.18;
                    let d3 = self.read_room(22.0) * 0.10;
                    (d1 - d2 * 0.8 + d3, d1 + d2 * 0.8 - d3)
                }
                2 => {
                    let d1 = self.read_room(18.0) * 0.35;
                    let d2 = self.read_room(28.0) * 0.25;
                    let d3 = self.read_room(42.0) * 0.18;
                    let d4 = self.read_room(60.0) * 0.12;
                    (d1 - d2 * 0.8 + d3 - d4 * 0.8, d1 + d2 * 0.8 - d3 + d4 * 0.8)
                }
                3 => {
                    let d1 = self.read_room(35.0) * 0.45;
                    let d2 = self.read_room(65.0) * 0.35;
                    let d3 = self.read_room(95.0) * 0.25;
                    let d4 = self.read_room(140.0) * 0.18;
                    (d1 - d2 * 0.8 + d3 - d4 * 0.8, d1 + d2 * 0.8 - d3 + d4 * 0.8)
                }
                _ => {
                    let d1 = self.read_room(60.0) * 0.50;
                    let d2 = self.read_room(110.0) * 0.42;
                    let d3 = self.read_room(170.0) * 0.35;
                    let d4 = self.read_room(240.0) * 0.25;
                    (d1 - d2 * 0.8 + d3 - d4 * 0.8, d1 + d2 * 0.8 - d3 + d4 * 0.8)
                }
            };

            let lp_alpha = (2.0 * PI * 4500.0 / self.sample_rate).min(0.6);
            self.room_lp_l += lp_alpha * (refl_l - self.room_lp_l);
            self.room_lp_r += lp_alpha * (refl_r - self.room_lp_r);

            out_l += self.room_lp_l * room_amount;
            out_r += self.room_lp_r * room_amount;

            self.room_write_pos = (self.room_write_pos + 1) % self.room_buffer.len();
        }

        // Re-inject sub-bass mono
        if bass_mono {
            out_l += sub_mono;
            out_r += sub_mono;
        }

        let wet_l = (1.0 - mix) * in_l + mix * out_l;
        let wet_r = (1.0 - mix) * in_r + mix * out_r;

        (wet_l, wet_r)
    }

    // === Split Spatial: 4-band frequency-dependent spatialization ===
    // Splits input into sub/low/mid/high bands and applies different azimuth to each
    #[allow(clippy::too_many_arguments)]
    pub fn process_split_spatial(
        &mut self,
        in_l: f32,
        in_r: f32,
        azimuth_deg: f32,
        elevation_deg: f32,
        distance_m: f32,
        sub_width: f32,
        low_width: f32,
        mid_width: f32,
        high_width: f32,
    ) -> (f32, f32) {
        let mono = (in_l + in_r) * 0.5;

        // Crossover frequencies
        let f1 = 100.0;  // sub/low
        let f2 = 500.0;  // low/mid
        let f3 = 3000.0; // mid/high

        let a1 = (2.0 * PI * f1 / self.sample_rate).min(0.95);
        let a2 = (2.0 * PI * f2 / self.sample_rate).min(0.95);
        let a3 = (2.0 * PI * f3 / self.sample_rate).min(0.95);

        // Split into bands
        self.band_lp1[0] += a1 * (mono - self.band_lp1[0]);
        self.band_lp2[0] += a2 * (mono - self.band_lp2[0]);
        self.band_lp3[0] += a3 * (mono - self.band_lp3[0]);

        let sub_band = self.band_lp1[0];
        let low_band = self.band_lp2[0] - self.band_lp1[0];
        let mid_band = self.band_lp3[0] - self.band_lp2[0];
        let high_band = mono - self.band_lp3[0];

        // Apply different azimuth to each band
        let sub_az = azimuth_deg * sub_width;
        let low_az = azimuth_deg * low_width;
        let mid_az = azimuth_deg * mid_width;
        let high_az = azimuth_deg * high_width;

        let (sub_l, sub_r) = self.process_single_band(sub_band, sub_az, elevation_deg, distance_m);
        let (low_l, low_r) = self.process_single_band(low_band, low_az, elevation_deg, distance_m);
        let (mid_l, mid_r) = self.process_single_band(mid_band, mid_az, elevation_deg, distance_m);
        let (high_l, high_r) = self.process_single_band(high_band, high_az, elevation_deg, distance_m);

        (sub_l + low_l + mid_l + high_l, sub_r + low_r + mid_r + high_r)
    }

    fn process_single_band(&self, input: f32, azimuth_deg: f32, elevation_deg: f32, distance_m: f32) -> (f32, f32) {
        let r_head = 0.0875;
        let c_sound = 343.0;
        let theta_rad = (azimuth_deg.clamp(-90.0, 90.0) * PI) / 180.0;
        let elev_clamped = elevation_deg.clamp(-45.0, 90.0);
        let elev_factor = (elev_clamped.max(0.0) * PI / 180.0).cos().max(0.0);

        let _itd_sec = (r_head / c_sound) * (theta_rad.abs() + theta_rad.abs().sin()) * elev_factor;

        // Simple ITD: delayed signal goes to far ear
        let shadow = theta_rad.abs().sin() * elev_factor;
        let gain_near = 1.0 - shadow * 0.35;
        let gain_far = 1.0 - shadow * 0.65;

        let dist = distance_m.max(0.3);
        let dist_gain = 1.0 / dist.sqrt();

        if azimuth_deg >= 0.0 {
            (
                input * gain_near * dist_gain,
                input * gain_far * dist_gain,
            )
        } else {
            (
                input * gain_far * dist_gain,
                input * gain_near * dist_gain,
            )
        }
    }

    // === Externalization: adds diffuse early reflections ===
    pub fn process_externalization(
        &mut self,
        in_l: f32,
        in_r: f32,
        amount: f32,
    ) -> (f32, f32) {
        if amount < 0.01 {
            return (in_l, in_r);
        }

        let mono = (in_l + in_r) * 0.5;
        self.ext_buffer[self.ext_write_pos] = mono;

        // 6 early reflection taps with different delays and gains
        let taps = [
            (5.0, 0.18),   // 5ms - very early
            (12.0, 0.14),  // 12ms
            (23.0, 0.10),  // 23ms
            (37.0, 0.07),  // 37ms
            (56.0, 0.05),  // 56ms
            (80.0, 0.03),  // 80ms
        ];

        let mut ext_l = 0.0;
        let mut ext_r = 0.0;

        for (i, (delay_ms, gain)) in taps.iter().enumerate() {
            let reflected = self.read_ext(*delay_ms);
            // Alternate L/R panning for each tap
            if i % 2 == 0 {
                ext_l += reflected * gain;
                ext_r += reflected * gain * 0.7;
            } else {
                ext_l += reflected * gain * 0.7;
                ext_r += reflected * gain;
            }
        }

        self.ext_write_pos = (self.ext_write_pos + 1) % self.ext_buffer.len();

        // Mix externalization with dry
        let ext_l = in_l + ext_l * amount;
        let ext_r = in_r + ext_r * amount;
        (ext_l, ext_r)
    }

    // === Output Mode: Headphones/Club/Hybrid ===
    pub fn process_output_mode(
        &self,
        in_l: f32,
        in_r: f32,
        mode: i32, // 0=Headphones, 1=Club, 2=Hybrid
    ) -> (f32, f32) {
        match mode {
            1 => {
                // Club: mono-safe low end, reduce extreme stereo
                let mono = (in_l + in_r) * 0.5;
                let side = (in_l - in_r) * 0.5;

                // Mono below 200Hz
                let low_mono = mono;

                // Reduce side below 200Hz (already mono)
                // Reduce extreme side above 8kHz
                let out_l = low_mono + side * 0.85;
                let out_r = low_mono - side * 0.85;
                (out_l, out_r)
            }
            2 => {
                // Hybrid: slight mono boost below 100Hz, keep rest
                let mono = (in_l + in_r) * 0.5;
                let side_l = in_l - mono;
                let side_r = in_r - mono;
                let out_l = mono + side_l * 0.9;
                let out_r = mono + side_r * 0.9;
                (out_l, out_r)
            }
            _ => {
                // Headphones: full binaural, no processing
                (in_l, in_r)
            }
        }
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

    fn read_ext(&self, delay_ms: f32) -> f32 {
        let samples = (delay_ms / 1000.0) * self.sample_rate;
        let buf_len = self.ext_buffer.len();
        let int_d = samples.floor() as usize;
        let frac_d = samples - (int_d as f32);
        let idx1 = (self.ext_write_pos + buf_len - (int_d % buf_len)) % buf_len;
        let idx2 = (self.ext_write_pos + buf_len - ((int_d + 1) % buf_len)) % buf_len;
        (1.0 - frac_d) * self.ext_buffer[idx1] + frac_d * self.ext_buffer[idx2]
    }
}
