// Stereo Eblet 3D - Binaural 3D Head Spatializer & HRTF Psychoacoustic VST3 / CLAP plugin.
pub mod dsp;
pub mod editor;
pub mod gui_state;
pub mod wgpu_editor;

use dsp::SpatializerDsp;
use nih_plug::prelude::*;
use std::sync::Arc;

pub struct StereoEblet3D {
    params: Arc<StereoEblet3DParams>,
    dsp: SpatializerDsp,
    sample_rate: f32,
}

#[derive(Params)]
pub struct StereoEblet3DParams {
    #[persist = "editor-state"]
    pub editor_state: Arc<wgpu_editor::WgpuEditorState>,

    #[id = "head_pos"]
    pub head_position: FloatParam,

    #[id = "azimuth"]
    pub azimuth: FloatParam,

    #[id = "elevation"]
    pub elevation: FloatParam,

    #[id = "distance"]
    pub distance: FloatParam,

    #[id = "bass_mono"]
    pub bass_mono: BoolParam,

    #[id = "room_model"]
    pub room_model: IntParam,

    #[id = "room_amount"]
    pub room_amount: FloatParam,

    #[id = "mix"]
    pub mix: FloatParam,

    #[id = "genre"]
    pub genre: IntParam,

    #[id = "source_type"]
    pub source_type: IntParam,

    #[id = "depth_zone"]
    pub depth_zone: IntParam,

    #[id = "output_mode"]
    pub output_mode: IntParam,

    #[id = "split_spatial"]
    pub split_spatial: BoolParam,

    #[id = "sub_width"]
    pub sub_width: FloatParam,

    #[id = "low_width"]
    pub low_width: FloatParam,

    #[id = "mid_width"]
    pub mid_width: FloatParam,

    #[id = "high_width"]
    pub high_width: FloatParam,

    #[id = "externalization"]
    pub externalization: FloatParam,
}

impl Default for StereoEblet3D {
    fn default() -> Self {
        Self {
            params: Arc::new(StereoEblet3DParams::default()),
            dsp: SpatializerDsp::new(44100.0),
            sample_rate: 44100.0,
        }
    }
}

impl Default for StereoEblet3DParams {
    fn default() -> Self {
        Self {
            editor_state: wgpu_editor::WgpuEditorState::from_size((900, 600)),

            head_position: FloatParam::new(
                "Head Trajectory",
                0.66,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            )
            .with_unit(" (Neck->Face)"),

            azimuth: FloatParam::new(
                "Azimuth",
                30.0,
                FloatRange::Linear { min: -90.0, max: 90.0 },
            )
            .with_unit(" deg"),

            elevation: FloatParam::new(
                "Elevation (Height)",
                0.0,
                FloatRange::Linear { min: -45.0, max: 90.0 },
            )
            .with_unit(" deg (Neck->Crown)"),

            distance: FloatParam::new(
                "Distance",
                1.0,
                FloatRange::Linear { min: 0.3, max: 3.0 },
            )
            .with_unit(" m"),

            bass_mono: BoolParam::new("Mono-Maker (<120Hz)", true),

            room_model: IntParam::new(
                "Room Model",
                2,
                IntRange::Linear { min: 0, max: 4 },
            ),

            room_amount: FloatParam::new(
                "Room Amount",
                0.25,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            )
            .with_unit("%"),

            mix: FloatParam::new(
                "Dry/Wet Mix",
                1.0,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            )
            .with_unit("%"),

            genre: IntParam::new(
                "Genre",
                0,
                IntRange::Linear { min: 0, max: 8 },
            ),

            source_type: IntParam::new(
                "Source Type",
                0,
                IntRange::Linear { min: 0, max: 7 },
            ),

            depth_zone: IntParam::new(
                "Depth Zone",
                1,
                IntRange::Linear { min: 0, max: 2 },
            ),

            output_mode: IntParam::new(
                "Output Mode",
                0,
                IntRange::Linear { min: 0, max: 2 },
            ),

            split_spatial: BoolParam::new("Split Spatial", false),

            sub_width: FloatParam::new(
                "Sub Width",
                0.0,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            ),

            low_width: FloatParam::new(
                "Low Width",
                0.1,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            ),

            mid_width: FloatParam::new(
                "Mid Width",
                0.3,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            ),

            high_width: FloatParam::new(
                "High Width",
                0.6,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            ),

            externalization: FloatParam::new(
                "Externalization",
                0.5,
                FloatRange::Linear { min: 0.0, max: 1.0 },
            ),
        }
    }
}

impl Plugin for StereoEblet3D {
    const NAME: &'static str = "Stereo Eblet 3D";
    const VENDOR: &'static str = "MusicMixCode";
    const URL: &'static str = "https://github.com/MusicMixCode";
    const EMAIL: &'static str = "info@musicmixcode.com";
    const VERSION: &'static str = "1.0.0";

    const AUDIO_IO_LAYOUTS: &'static [AudioIOLayout] = &[AudioIOLayout {
        main_input_channels: NonZeroU32::new(2),
        main_output_channels: NonZeroU32::new(2),
        ..AudioIOLayout::const_default()
    }];

    const MIDI_INPUT: MidiConfig = MidiConfig::None;
    const SAMPLE_ACCURATE_AUTOMATION: bool = true;

    type SysExMessage = ();
    type BackgroundTask = ();

    fn params(&self) -> Arc<dyn Params> {
        self.params.clone()
    }

    fn editor(&mut self, _async_executor: AsyncExecutor<Self>) -> Option<Box<dyn Editor>> {
        Some(Box::new(wgpu_editor::WgpuEditor::new(
            self.params.clone(),
            self.params.editor_state.clone(),
        )))
    }

    fn initialize(
        &mut self,
        _audio_io_layout: &AudioIOLayout,
        buffer_config: &BufferConfig,
        _context: &mut impl InitContext<Self>,
    ) -> bool {
        self.dsp.set_sample_rate(buffer_config.sample_rate);
        self.sample_rate = buffer_config.sample_rate;
        true
    }

    fn process(
        &mut self,
        buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        _context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        let start = std::time::Instant::now();
        let head_pos = self.params.head_position.value();
        let azimuth = self.params.azimuth.value();
        let elevation = self.params.elevation.value();
        let distance = self.params.distance.value();
        let bass_mono = self.params.bass_mono.value();
        let room_model = self.params.room_model.value();
        let room_amount = self.params.room_amount.value();
        let mix = self.params.mix.value();
        let split_spatial = self.params.split_spatial.value();
        let sub_width = self.params.sub_width.value();
        let low_width = self.params.low_width.value();
        let mid_width = self.params.mid_width.value();
        let high_width = self.params.high_width.value();
        let externalization = self.params.externalization.value();
        let output_mode = self.params.output_mode.value();

        let mut sample_count = 0u32;
        for channel_samples in buffer.iter_samples() {
            sample_count += 1;
            let mut samples_iter = channel_samples.into_iter();
            let l_sample = samples_iter.next().unwrap();
            let r_sample = samples_iter.next().unwrap();

            let (mut out_l, mut out_r) = if split_spatial {
                self.dsp.process_split_spatial(
                    *l_sample,
                    *r_sample,
                    azimuth,
                    elevation,
                    distance,
                    sub_width,
                    low_width,
                    mid_width,
                    high_width,
                )
            } else {
                self.dsp.process_frame(
                    *l_sample,
                    *r_sample,
                    head_pos,
                    azimuth,
                    elevation,
                    distance,
                    bass_mono,
                    room_model,
                    room_amount,
                    mix,
                )
            };

            // Externalization
            if externalization > 0.01 {
                let (ext_l, ext_r) = self.dsp.process_externalization(out_l, out_r, externalization);
                out_l = ext_l;
                out_r = ext_r;
            }

            // Output mode
            let (mode_l, mode_r) = self.dsp.process_output_mode(out_l, out_r, output_mode);
            out_l = mode_l;
            out_r = mode_r;

            *l_sample = out_l;
            *r_sample = out_r;
        }

        let elapsed = start.elapsed().as_secs_f32();
        let available_time = sample_count as f32 / self.sample_rate;
        let cpu = if available_time > 0.0 { (elapsed / available_time * 100.0).min(100.0) } else { 0.0 };
        self.params.editor_state.set_cpu_usage(cpu);

        ProcessStatus::Normal
    }
}

impl ClapPlugin for StereoEblet3D {
    const CLAP_ID: &'static str = "com.musicmixcode.stereoeblet3d";
    const CLAP_DESCRIPTION: Option<&'static str> =
        Some("Stereo Eblet 3D - Binaural 3D Head Spatializer & HRTF Psychoacoustic Positioning");
    const CLAP_MANUAL_URL: Option<&'static str> = None;
    const CLAP_SUPPORT_URL: Option<&'static str> = None;
    const CLAP_FEATURES: &'static [ClapFeature] = &[
        ClapFeature::AudioEffect,
        ClapFeature::Stereo,
        ClapFeature::Custom("spatial"),
    ];
}

impl Vst3Plugin for StereoEblet3D {
    const VST3_CLASS_ID: [u8; 16] = *b"StereoEblet3D001";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[
        Vst3SubCategory::Fx,
        Vst3SubCategory::Spatial,
        Vst3SubCategory::Stereo,
    ];
}

nih_export_clap!(StereoEblet3D);
nih_export_vst3!(StereoEblet3D);

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gui_state::GuiState;

    #[test]
    fn test_plugin_creation() {
        let plugin = StereoEblet3D::default();
        let params = StereoEblet3DParams::default();
        
        assert_eq!(params.head_position.default_plain_value(), 0.66);
        assert_eq!(params.azimuth.default_plain_value(), 30.0);
        assert_eq!(params.elevation.default_plain_value(), 0.0);
        assert_eq!(params.distance.default_plain_value(), 1.0);
        assert!(params.bass_mono.default_plain_value());
        assert_eq!(params.room_model.default_plain_value(), 2);
        assert_eq!(params.room_amount.default_plain_value(), 0.25);
        assert_eq!(params.mix.default_plain_value(), 1.0);
        
        assert_eq!(plugin.params().as_ref().param_map().len(), 18);
    }

    #[test]
    fn test_dsp_basic() {
        let mut dsp = SpatializerDsp::new(44100.0);
        
        let (out_l, out_r) = dsp.process_frame(
            0.5, 0.5,
            0.66,
            30.0,
            0.0,
            1.0,
            true,
            2,
            0.25,
            1.0,
        );
        
        assert!(out_l.is_finite());
        assert!(out_r.is_finite());
    }

    #[test]
    fn test_gui_state() {
        let state = GuiState::new();
        assert_eq!(state.params.position.azimuth, 0.0);
        assert_eq!(state.params.position.elevation, 0.0);
        assert_eq!(state.params.position.distance, 1.0);
    }
}
