// Stereo Eblet 3D Concept 2 - Binaural 3D Head Spatializer & HRTF Psychoacoustic VST3 / CLAP plugin.
pub mod dsp;
pub mod editor;
pub mod gui_state;

use dsp::SpatializerDsp;
use nih_plug::prelude::*;
use std::sync::Arc;

pub struct StereoEblet3DConcept2 {
    params: Arc<StereoEblet3DConcept2Params>,
    dsp: SpatializerDsp,
    egui_state: Arc<nih_plug_egui::EguiState>,
}

#[derive(Params)]
pub struct StereoEblet3DConcept2Params {
    #[id = "head_pos"]
    pub head_position: FloatParam,

    #[id = "azimuth"]
    pub azimuth: FloatParam,

    #[id = "elevation"]
    pub elevation: FloatParam,

    #[id = "distance"]
    pub distance: FloatParam,

    #[id = "split_spatial"]
    pub split_spatial: IntParam,

    #[id = "club_safe"]
    pub club_safe: BoolParam,

    #[id = "room_model"]
    pub room_model: IntParam,

    #[id = "room_amount"]
    pub room_amount: FloatParam,

    #[id = "mix"]
    pub mix: FloatParam,
}

impl Default for StereoEblet3DConcept2 {
    fn default() -> Self {
        Self {
            params: Arc::new(StereoEblet3DConcept2Params::default()),
            dsp: SpatializerDsp::new(44100.0),
            egui_state: nih_plug_egui::EguiState::from_size(1376, 768),
        }
    }
}

impl Default for StereoEblet3DConcept2Params {
    fn default() -> Self {
        Self {
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

            split_spatial: IntParam::new(
                "Split Spatial",
                1,
                IntRange::Linear { min: 0, max: 2 },
            ),

            club_safe: BoolParam::new("Club Safe Mode", false),

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
        }
    }
}

impl Plugin for StereoEblet3DConcept2 {
    const NAME: &'static str = "BINAURAL EBLET 3d concept 2";
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
        editor::create_editor(self.egui_state.clone(), self.params.clone())
    }

    fn initialize(
        &mut self,
        _audio_io_layout: &AudioIOLayout,
        buffer_config: &BufferConfig,
        _context: &mut impl InitContext<Self>,
    ) -> bool {
        self.dsp.set_sample_rate(buffer_config.sample_rate);
        true
    }

    fn process(
        &mut self,
        buffer: &mut Buffer,
        _aux: &mut AuxiliaryBuffers,
        _context: &mut impl ProcessContext<Self>,
    ) -> ProcessStatus {
        let head_pos = self.params.head_position.value();
        let azimuth = self.params.azimuth.value();
        let elevation = self.params.elevation.value();
        let distance = self.params.distance.value();
        let split_spatial = self.params.split_spatial.value();
        let club_safe = self.params.club_safe.value();
        let room_model = self.params.room_model.value();
        let room_amount = self.params.room_amount.value();
        let mix = self.params.mix.value();

        for channel_samples in buffer.iter_samples() {
            let mut samples_iter = channel_samples.into_iter();
            let l_sample = samples_iter.next().unwrap();
            let r_sample = samples_iter.next().unwrap();

            let (out_l, out_r) = self.dsp.process_frame(
                *l_sample,
                *r_sample,
                head_pos,
                azimuth,
                elevation,
                distance,
                split_spatial,
                club_safe,
                room_model,
                room_amount,
                mix,
            );

            *l_sample = out_l;
            *r_sample = out_r;
        }

        ProcessStatus::Normal
    }
}

impl ClapPlugin for StereoEblet3DConcept2 {
    const CLAP_ID: &'static str = "com.musicmixcode.stereoeblet3d-concept2";
    const CLAP_DESCRIPTION: Option<&'static str> =
        Some("Stereo Eblet 3D Concept 2 - Binaural 3D Head Spatializer & HRTF Psychoacoustic Positioning");
    const CLAP_MANUAL_URL: Option<&'static str> = None;
    const CLAP_SUPPORT_URL: Option<&'static str> = None;
    const CLAP_FEATURES: &'static [ClapFeature] = &[
        ClapFeature::AudioEffect,
        ClapFeature::Stereo,
        ClapFeature::Custom("spatial"),
    ];
}

impl Vst3Plugin for StereoEblet3DConcept2 {
    const VST3_CLASS_ID: [u8; 16] = *b"StEblet3DC2_0001";
    const VST3_SUBCATEGORIES: &'static [Vst3SubCategory] = &[
        Vst3SubCategory::Fx,
        Vst3SubCategory::Spatial,
        Vst3SubCategory::Stereo,
    ];
}

nih_export_clap!(StereoEblet3DConcept2);
nih_export_vst3!(StereoEblet3DConcept2);
