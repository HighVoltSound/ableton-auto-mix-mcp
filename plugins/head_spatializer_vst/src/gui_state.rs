use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum Genre {
    Techno,
    House,
    Psytrance,
    Trance,
    DnB,
    Dubstep,
    Trap,
    FutureBass,
    Ambient,
}

impl Genre {
    pub const ALL: &'static [Genre] = &[
        Genre::Techno,
        Genre::House,
        Genre::Psytrance,
        Genre::Trance,
        Genre::DnB,
        Genre::Dubstep,
        Genre::Trap,
        Genre::FutureBass,
        Genre::Ambient,
    ];

    pub fn label(&self) -> &'static str {
        match self {
            Genre::Techno => "Techno",
            Genre::House => "House",
            Genre::Psytrance => "Psytrance",
            Genre::Trance => "Trance",
            Genre::DnB => "DnB",
            Genre::Dubstep => "Dubstep",
            Genre::Trap => "Trap",
            Genre::FutureBass => "Future Bass",
            Genre::Ambient => "Ambient",
        }
    }

    pub fn index(&self) -> usize {
        Self::ALL.iter().position(|g| g == self).unwrap_or(0)
    }

    pub fn from_index(i: usize) -> Self {
        Self::ALL.get(i).copied().unwrap_or(Genre::Techno)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum SourceType {
    Kick,
    Bass,
    Lead,
    Pad,
    Hat,
    Perc,
    Fx,
    Vocal,
}

impl SourceType {
    pub const ALL: &'static [SourceType] = &[
        SourceType::Kick,
        SourceType::Bass,
        SourceType::Lead,
        SourceType::Pad,
        SourceType::Hat,
        SourceType::Perc,
        SourceType::Fx,
        SourceType::Vocal,
    ];

    pub fn label(&self) -> &'static str {
        match self {
            SourceType::Kick => "Kick",
            SourceType::Bass => "Bass",
            SourceType::Lead => "Lead",
            SourceType::Pad => "Pad",
            SourceType::Hat => "Hat",
            SourceType::Perc => "Perc",
            SourceType::Fx => "FX",
            SourceType::Vocal => "Vocal",
        }
    }

    pub fn index(&self) -> usize {
        Self::ALL.iter().position(|s| s == self).unwrap_or(0)
    }

    pub fn from_index(i: usize) -> Self {
        Self::ALL.get(i).copied().unwrap_or(SourceType::Kick)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum DepthZone {
    Front,
    Mid,
    Back,
}

impl DepthZone {
    pub const ALL: &'static [DepthZone] = &[DepthZone::Front, DepthZone::Mid, DepthZone::Back];

    pub fn label(&self) -> &'static str {
        match self {
            DepthZone::Front => "Front",
            DepthZone::Mid => "Mid",
            DepthZone::Back => "Back",
        }
    }

    pub fn index(&self) -> usize {
        Self::ALL.iter().position(|d| d == self).unwrap_or(0)
    }

    pub fn from_index(i: usize) -> Self {
        Self::ALL.get(i).copied().unwrap_or(DepthZone::Mid)
    }

    pub fn distance_range(&self) -> (f32, f32) {
        match self {
            DepthZone::Front => (0.1, 1.0),
            DepthZone::Mid => (1.0, 3.0),
            DepthZone::Back => (3.0, 15.0),
        }
    }

    pub fn drr(&self) -> f32 {
        match self {
            DepthZone::Front => 0.9,
            DepthZone::Mid => 0.6,
            DepthZone::Back => 0.3,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum OutputMode {
    Headphones,
    Club,
    Hybrid,
}

impl OutputMode {
    pub const ALL: &'static [OutputMode] = &[
        OutputMode::Headphones,
        OutputMode::Club,
        OutputMode::Hybrid,
    ];

    pub fn label(&self) -> &'static str {
        match self {
            OutputMode::Headphones => "Headphones",
            OutputMode::Club => "Club",
            OutputMode::Hybrid => "Hybrid",
        }
    }

    pub fn index(&self) -> usize {
        Self::ALL.iter().position(|m| m == self).unwrap_or(0)
    }

    pub fn from_index(i: usize) -> Self {
        Self::ALL.get(i).copied().unwrap_or(OutputMode::Headphones)
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct SpatialTemplate {
    pub azimuth: f32,
    pub elevation: f32,
    pub distance: f32,
    pub width: f32,
    pub bass_mono: bool,
    pub room: RoomModel,
    pub room_amount: f32,
}

const fn tmpl(az: f32, el: f32, dist: f32, w: f32, bm: bool, rm: RoomModel, ra: f32) -> SpatialTemplate {
    SpatialTemplate { azimuth: az, elevation: el, distance: dist, width: w, bass_mono: bm, room: rm, room_amount: ra }
}

pub fn get_spatial_template(genre: Genre, source: SourceType) -> SpatialTemplate {
    let d = RoomModel::Dry;
    let b = RoomModel::Booth;
    let s = RoomModel::Studio;
    let c = RoomModel::Club;
    let k = RoomModel::Cathedral;

    let tables: [[SpatialTemplate; 8]; 9] = [
        // Techno: Kick/Bass centered, Pads wide, FX extreme
        [tmpl(0.0,-15.0,0.5,0.0,true,d,0.00), tmpl(0.0,-10.0,0.6,0.1,true,d,0.00), tmpl(0.0,5.0,0.8,0.3,false,s,0.20), tmpl(-70.0,60.0,2.5,1.0,false,k,0.50), tmpl(0.0,20.0,1.0,0.1,false,b,0.10), tmpl(-50.0,20.0,1.3,0.5,false,s,0.20), tmpl(-75.0,50.0,2.0,1.0,false,c,0.45), tmpl(0.0,10.0,0.7,0.2,false,s,0.22)],
        // House: Slightly wider hats/perc, centered kick
        [tmpl(0.0,-12.0,0.5,0.0,true,d,0.00), tmpl(0.0,-8.0,0.6,0.15,true,d,0.05), tmpl(0.0,12.0,0.8,0.4,false,s,0.22), tmpl(-60.0,50.0,2.2,1.0,false,c,0.45), tmpl(-10.0,25.0,1.0,0.1,false,b,0.12), tmpl(-40.0,20.0,1.2,0.5,false,s,0.20), tmpl(-65.0,45.0,2.0,1.0,false,c,0.40), tmpl(0.0,10.0,0.6,0.2,false,s,0.25)],
        // Psytrance: Very tight kick-bass, extreme FX wide
        [tmpl(0.0,-18.0,0.4,0.0,true,d,0.00), tmpl(0.0,-12.0,0.5,0.0,true,d,0.00), tmpl(0.0,8.0,0.7,0.3,false,s,0.18), tmpl(-65.0,55.0,2.3,1.0,false,k,0.50), tmpl(-5.0,22.0,1.0,0.05,false,b,0.08), tmpl(-45.0,18.0,1.2,0.4,false,s,0.18), tmpl(-80.0,60.0,2.5,1.0,false,c,0.50), tmpl(0.0,8.0,0.7,0.15,false,s,0.20)],
        // Trance: Wide supersaws/pads, centered low end
        [tmpl(0.0,-15.0,0.5,0.0,true,d,0.00), tmpl(0.0,-10.0,0.6,0.1,true,d,0.00), tmpl(0.0,15.0,0.7,0.3,false,s,0.22), tmpl(-65.0,65.0,2.8,1.0,false,k,0.55), tmpl(-8.0,20.0,1.0,0.08,false,b,0.10), tmpl(-50.0,25.0,1.3,0.5,false,s,0.22), tmpl(-70.0,55.0,2.2,1.0,false,c,0.45), tmpl(0.0,12.0,0.7,0.2,false,s,0.25)],
        // DnB: Upside-down triangle, Reese bass wide
        [tmpl(0.0,-18.0,0.4,0.0,true,d,0.00), tmpl(0.0,-12.0,0.5,0.0,true,d,0.00), tmpl(0.0,8.0,0.7,0.4,false,s,0.20), tmpl(-70.0,60.0,2.5,1.0,false,k,0.50), tmpl(-5.0,18.0,1.0,0.05,false,b,0.08), tmpl(-50.0,22.0,1.3,0.5,false,s,0.20), tmpl(-80.0,55.0,2.3,1.0,false,c,0.48), tmpl(0.0,10.0,0.7,0.15,false,s,0.22)],
        // Dubstep: Sub mono center, growl multi-band wide
        [tmpl(0.0,-20.0,0.4,0.0,true,d,0.00), tmpl(0.0,-15.0,0.5,0.0,true,d,0.00), tmpl(0.0,10.0,0.7,0.5,false,s,0.22), tmpl(-70.0,55.0,2.2,1.0,false,c,0.48), tmpl(-5.0,15.0,1.0,0.05,false,b,0.10), tmpl(-55.0,20.0,1.3,0.6,false,s,0.22), tmpl(-75.0,50.0,2.0,1.0,false,c,0.45), tmpl(0.0,8.0,0.7,0.15,false,s,0.20)],
        // Trap: Hard center, rolling hats wide
        [tmpl(0.0,-15.0,0.5,0.0,true,d,0.00), tmpl(0.0,-12.0,0.5,0.0,true,d,0.00), tmpl(0.0,10.0,0.7,0.35,false,s,0.20), tmpl(-60.0,50.0,2.0,1.0,false,c,0.42), tmpl(-8.0,20.0,1.0,0.08,false,b,0.10), tmpl(-45.0,22.0,1.2,0.5,false,s,0.20), tmpl(-70.0,48.0,2.0,1.0,false,c,0.42), tmpl(0.0,10.0,0.6,0.15,false,s,0.22)],
        // Future Bass: Wide supersaw chords, centered kick/snare
        [tmpl(0.0,-12.0,0.5,0.0,true,d,0.00), tmpl(0.0,-8.0,0.6,0.1,true,d,0.00), tmpl(0.0,15.0,0.7,0.4,false,s,0.25), tmpl(-65.0,60.0,2.5,1.0,false,k,0.50), tmpl(-10.0,22.0,1.0,0.1,false,b,0.12), tmpl(-50.0,25.0,1.3,0.5,false,s,0.22), tmpl(-65.0,50.0,2.2,1.0,false,c,0.45), tmpl(0.0,12.0,0.7,0.2,false,s,0.25)],
        // Ambient: Everything floats, even bass moves
        [tmpl(0.0,-5.0,1.0,0.2,false,s,0.30), tmpl(-20.0,0.0,1.5,0.5,false,s,0.35), tmpl(0.0,20.0,1.2,0.6,false,s,0.35), tmpl(-55.0,55.0,3.0,1.0,false,k,0.60), tmpl(-40.0,35.0,2.0,0.8,false,c,0.40), tmpl(-60.0,40.0,2.5,0.9,false,c,0.45), tmpl(-80.0,70.0,3.0,1.0,false,k,0.60), tmpl(0.0,15.0,1.0,0.5,false,s,0.30)],
    ];

    tables[genre.index()][source.index()]
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct OrbPosition {
    pub azimuth: f32,
    pub elevation: f32,
    pub distance: f32,
}

impl OrbPosition {
    pub fn new(azimuth: f32, elevation: f32, distance: f32) -> Self {
        Self {
            azimuth,
            elevation,
            distance,
        }
    }

    pub fn head_trajectory(&self) -> f32 {
        let t = (self.elevation + 45.0) / 135.0;
        t.clamp(0.0, 1.0)
    }

    pub fn clamp(&mut self) {
        self.azimuth = self.azimuth.clamp(-90.0, 90.0);
        self.elevation = self.elevation.clamp(-45.0, 90.0);
        self.distance = self.distance.clamp(0.3, 3.0);
    }
}

impl Default for OrbPosition {
    fn default() -> Self {
        Self::new(0.0, 0.0, 1.0)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum RoomModel {
    Dry = 0,
    Booth = 1,
    Studio = 2,
    Club = 3,
    Cathedral = 4,
}

impl RoomModel {
    pub fn from_index(i: i32) -> Self {
        match i {
            0 => Self::Dry,
            1 => Self::Booth,
            2 => Self::Studio,
            3 => Self::Club,
            4 => Self::Cathedral,
            _ => Self::Studio,
        }
    }

    pub fn label(&self) -> &'static str {
        match self {
            Self::Dry => "Dry",
            Self::Booth => "Booth",
            Self::Studio => "Studio",
            Self::Club => "Club",
            Self::Cathedral => "Cathedral",
        }
    }

    pub fn all() -> &'static [RoomModel] {
        &[
            Self::Dry,
            Self::Booth,
            Self::Studio,
            Self::Club,
            Self::Cathedral,
        ]
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preset {
    pub name: &'static str,
    pub position: OrbPosition,
    pub bass_mono: bool,
    pub room: RoomModel,
    pub room_amount: f32,
    pub mix: f32,
}

impl Preset {
    #[allow(clippy::too_many_arguments)]
    pub const fn new(
        name: &'static str,
        azimuth: f32,
        elevation: f32,
        distance: f32,
        bass_mono: bool,
        room: RoomModel,
        room_amount: f32,
        mix: f32,
    ) -> Self {
        Self {
            name,
            position: OrbPosition {
                azimuth,
                elevation,
                distance,
            },
            bass_mono,
            room,
            room_amount,
            mix,
        }
    }
}

pub const PRESETS: &[Preset] = &[
    // === DRUMS ===
    Preset::new("Kick", 0.0, -15.0, 0.5, true, RoomModel::Dry, 0.0, 1.0),
    Preset::new("Snare", 0.0, 5.0, 0.8, false, RoomModel::Studio, 0.20, 1.0),
    Preset::new("HiHats L", -45.0, 30.0, 1.0, false, RoomModel::Booth, 0.12, 1.0),
    Preset::new("HiHats R", 45.0, 30.0, 1.0, false, RoomModel::Booth, 0.12, 1.0),
    Preset::new("Shaker L", -50.0, 25.0, 1.2, false, RoomModel::Booth, 0.15, 1.0),
    Preset::new("Shaker R", 50.0, 25.0, 1.2, false, RoomModel::Booth, 0.15, 1.0),
    Preset::new("Tom Hi", -15.0, 10.0, 0.9, false, RoomModel::Studio, 0.18, 1.0),
    Preset::new("Tom Mid", 0.0, 5.0, 1.0, false, RoomModel::Studio, 0.18, 1.0),
    Preset::new("Tom Lo", 15.0, 0.0, 1.1, false, RoomModel::Studio, 0.18, 1.0),
    Preset::new("Perc L", -55.0, 20.0, 1.3, false, RoomModel::Studio, 0.20, 1.0),
    Preset::new("Perc R", 55.0, 20.0, 1.3, false, RoomModel::Studio, 0.20, 1.0),
    Preset::new("Cymbal L", -60.0, 50.0, 1.5, false, RoomModel::Club, 0.25, 1.0),
    Preset::new("Cymbal R", 60.0, 50.0, 1.5, false, RoomModel::Club, 0.25, 1.0),
    Preset::new("Clap", 0.0, 8.0, 0.7, false, RoomModel::Studio, 0.18, 1.0),
    Preset::new("Rim", -5.0, 10.0, 0.8, false, RoomModel::Studio, 0.15, 1.0),

    // === BASS ===
    Preset::new("Bass", 0.0, -10.0, 0.6, true, RoomModel::Dry, 0.0, 1.0),
    Preset::new("Sub Bass", 0.0, -20.0, 0.4, true, RoomModel::Dry, 0.0, 1.0),
    Preset::new("Bass Synth", -5.0, -8.0, 0.7, true, RoomModel::Booth, 0.10, 1.0),
    Preset::new("Bass Guitar", 5.0, -5.0, 0.8, true, RoomModel::Studio, 0.15, 1.0),

    // === GUITARS ===
    Preset::new("Guitar L", -65.0, 10.0, 1.0, false, RoomModel::Studio, 0.20, 1.0),
    Preset::new("Guitar R", 65.0, 10.0, 1.0, false, RoomModel::Studio, 0.20, 1.0),
    Preset::new("Acoustic L", -50.0, 15.0, 1.2, false, RoomModel::Studio, 0.25, 1.0),
    Preset::new("Acoustic R", 50.0, 15.0, 1.2, false, RoomModel::Studio, 0.25, 1.0),
    Preset::new("Guitar Solo", 20.0, 20.0, 0.8, false, RoomModel::Studio, 0.22, 1.0),

    // === KEYS / SYNTHS ===
    Preset::new("Piano L", -40.0, 12.0, 1.1, false, RoomModel::Studio, 0.22, 1.0),
    Preset::new("Piano R", 40.0, 12.0, 1.1, false, RoomModel::Studio, 0.22, 1.0),
    Preset::new("Keys Wide L", -55.0, 18.0, 1.4, false, RoomModel::Studio, 0.28, 1.0),
    Preset::new("Keys Wide R", 55.0, 18.0, 1.4, false, RoomModel::Studio, 0.28, 1.0),
    Preset::new("Synth Lead", 15.0, 15.0, 0.8, false, RoomModel::Studio, 0.25, 1.0),
    Preset::new("Synth Pluck L", -45.0, 20.0, 1.2, false, RoomModel::Booth, 0.18, 1.0),
    Preset::new("Synth Pluck R", 45.0, 20.0, 1.2, false, RoomModel::Booth, 0.18, 1.0),
    Preset::new("Pads Wide L", -70.0, 60.0, 2.5, false, RoomModel::Cathedral, 0.50, 1.0),
    Preset::new("Pads Wide R", 70.0, 60.0, 2.5, false, RoomModel::Cathedral, 0.50, 1.0),
    Preset::new("Arp L", -50.0, 35.0, 1.3, false, RoomModel::Studio, 0.25, 1.0),
    Preset::new("Arp R", 50.0, 35.0, 1.3, false, RoomModel::Studio, 0.25, 1.0),

    // === VOCALS ===
    Preset::new("Lead Vocal", 0.0, 10.0, 0.6, false, RoomModel::Studio, 0.25, 1.0),
    Preset::new("Vocal L", -15.0, 10.0, 0.7, false, RoomModel::Studio, 0.22, 1.0),
    Preset::new("Vocal R", 15.0, 10.0, 0.7, false, RoomModel::Studio, 0.22, 1.0),
    Preset::new("Backing L", -25.0, 8.0, 0.9, false, RoomModel::Studio, 0.28, 1.0),
    Preset::new("Backing R", 25.0, 8.0, 0.9, false, RoomModel::Studio, 0.28, 1.0),
    Preset::new("Choir L", -40.0, 40.0, 2.0, false, RoomModel::Cathedral, 0.45, 1.0),
    Preset::new("Choir R", 40.0, 40.0, 2.0, false, RoomModel::Cathedral, 0.45, 1.0),
    Preset::new("Rap Vocal", 0.0, 5.0, 0.5, false, RoomModel::Booth, 0.12, 1.0),

    // === FX / ATMOSPHERE ===
    Preset::new("FX Wide L", -75.0, 50.0, 2.2, false, RoomModel::Club, 0.40, 1.0),
    Preset::new("FX Wide R", 75.0, 50.0, 2.2, false, RoomModel::Club, 0.40, 1.0),
    Preset::new("FX Center", 0.0, 30.0, 1.8, false, RoomModel::Studio, 0.35, 1.0),
    Preset::new("Atmos L", -65.0, 70.0, 2.8, false, RoomModel::Cathedral, 0.55, 1.0),
    Preset::new("Atmos R", 65.0, 70.0, 2.8, false, RoomModel::Cathedral, 0.55, 1.0),
    Preset::new("Sweep", 0.0, 45.0, 1.5, false, RoomModel::Club, 0.30, 1.0),
    Preset::new("Riser", 0.0, 60.0, 1.8, false, RoomModel::Studio, 0.35, 1.0),
    Preset::new("Impact", 0.0, -10.0, 1.0, false, RoomModel::Club, 0.40, 1.0),
    Preset::new("Riser Stereo L", -40.0, 55.0, 2.0, false, RoomModel::Studio, 0.30, 1.0),
    Preset::new("Riser Stereo R", 40.0, 55.0, 2.0, false, RoomModel::Studio, 0.30, 1.0),

    // === UTILITY ===
    Preset::new("Center Mono", 0.0, 0.0, 1.0, true, RoomModel::Dry, 0.0, 1.0),
    Preset::new("Wide L", -80.0, 0.0, 1.5, false, RoomModel::Studio, 0.30, 1.0),
    Preset::new("Wide R", 80.0, 0.0, 1.5, false, RoomModel::Studio, 0.30, 1.0),
    Preset::new("Behind", 0.0, -30.0, 1.2, false, RoomModel::Studio, 0.25, 1.0),
    Preset::new("Above", 0.0, 75.0, 1.5, false, RoomModel::Studio, 0.30, 1.0),
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllParams {
    pub position: OrbPosition,
    pub bass_mono: bool,
    pub room: RoomModel,
    pub room_amount: f32,
    pub mix: f32,

    pub genre: Genre,
    pub source_type: SourceType,
    pub depth_zone: DepthZone,
    pub output_mode: OutputMode,

    pub split_spatial: bool,
    pub sub_width: f32,
    pub low_width: f32,
    pub mid_width: f32,
    pub high_width: f32,

    pub externalization: f32,
}

impl AllParams {
    pub fn head_trajectory(&self) -> f32 {
        self.position.head_trajectory()
    }

    pub fn apply_genre_source(&mut self, genre: Genre, source: SourceType) {
        self.genre = genre;
        self.source_type = source;
        let tmpl = get_spatial_template(genre, source);
        self.position = OrbPosition::new(tmpl.azimuth, tmpl.elevation, tmpl.distance);
        self.bass_mono = tmpl.bass_mono;
        self.room = tmpl.room;
        self.room_amount = tmpl.room_amount;
    }

    pub fn apply_depth_zone(&mut self, zone: DepthZone) {
        self.depth_zone = zone;
        let (min_d, max_d) = zone.distance_range();
        let current = self.position.distance;
        self.position.distance = current.clamp(min_d, max_d);
    }

    pub fn apply_split_spatial_for_genre(&mut self) {
        match self.genre {
            Genre::DnB | Genre::Dubstep => {
                self.sub_width = 0.0;
                self.low_width = 0.15;
                self.mid_width = 0.40;
                self.high_width = 0.75;
            }
            Genre::Techno | Genre::House => {
                self.sub_width = 0.0;
                self.low_width = 0.10;
                self.mid_width = 0.30;
                self.high_width = 0.60;
            }
            Genre::Trance | Genre::Psytrance => {
                self.sub_width = 0.0;
                self.low_width = 0.10;
                self.mid_width = 0.35;
                self.high_width = 0.80;
            }
            Genre::Trap | Genre::FutureBass => {
                self.sub_width = 0.0;
                self.low_width = 0.05;
                self.mid_width = 0.35;
                self.high_width = 0.70;
            }
            Genre::Ambient => {
                self.sub_width = 0.20;
                self.low_width = 0.40;
                self.mid_width = 0.65;
                self.high_width = 0.90;
            }
        }
    }
}

impl Default for AllParams {
    fn default() -> Self {
        Self {
            position: OrbPosition::default(),
            bass_mono: true,
            room: RoomModel::Studio,
            room_amount: 0.25,
            mix: 1.0,

            genre: Genre::Techno,
            source_type: SourceType::Kick,
            depth_zone: DepthZone::Mid,
            output_mode: OutputMode::Headphones,

            split_spatial: false,
            sub_width: 0.0,
            low_width: 0.10,
            mid_width: 0.30,
            high_width: 0.60,

            externalization: 0.5,
        }
    }
}

#[derive(Debug, Clone)]
pub struct ABSlots {
    pub slot_a: AllParams,
    pub slot_b: AllParams,
    pub active: char,
}

impl ABSlots {
    pub fn new() -> Self {
        Self {
            slot_a: AllParams::default(),
            slot_b: AllParams::default(),
            active: 'A',
        }
    }

    pub fn current(&self) -> &AllParams {
        match self.active {
            'A' => &self.slot_a,
            'B' => &self.slot_b,
            _ => &self.slot_a,
        }
    }

    pub fn current_mut(&mut self) -> &mut AllParams {
        match self.active {
            'A' => &mut self.slot_a,
            'B' => &mut self.slot_b,
            _ => &mut self.slot_a,
        }
    }

    pub fn toggle(&mut self) {
        self.active = match self.active {
            'A' => 'B',
            'B' => 'A',
            _ => 'A',
        };
    }

    pub fn snapshot_to_inactive(&mut self) {
        let snapshot = self.current().clone();
        match self.active {
            'A' => self.slot_b = snapshot,
            'B' => self.slot_a = snapshot,
            _ => {}
        };
    }
}

impl Default for ABSlots {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone)]
pub struct GuiState {
    pub params: AllParams,
    pub ab: ABSlots,
    pub preset_index: usize,
    pub bypassed: bool,
    pub camera_rotation: (f32, f32),
    pub show_preset_browser: bool,
    pub preset_search: String,
    pub cpu_usage: f32,
    pub show_save_dialog: bool,
    pub preset_name_input: String,
    pub show_load_dialog: bool,
    pub show_help: bool,
}

impl GuiState {
    pub fn new() -> Self {
        Self {
            params: AllParams::default(),
            ab: ABSlots::new(),
            preset_index: 0,
            bypassed: false,
            camera_rotation: (0.3, 0.2),
            show_preset_browser: false,
            preset_search: String::new(),
            cpu_usage: 0.0,
            show_save_dialog: false,
            preset_name_input: String::new(),
            show_load_dialog: false,
            show_help: false,
        }
    }

    pub fn load_preset(&mut self, index: usize) {
        if let Some(preset) = PRESETS.get(index) {
            self.params = AllParams {
                position: preset.position,
                bass_mono: preset.bass_mono,
                room: preset.room,
                room_amount: preset.room_amount,
                mix: preset.mix,
                ..self.params.clone()
            };
            self.preset_index = index;
        }
    }

    pub fn next_preset(&mut self) {
        let next = (self.preset_index + 1) % PRESETS.len();
        self.load_preset(next);
    }

    pub fn prev_preset(&mut self) {
        let prev = if self.preset_index == 0 {
            PRESETS.len() - 1
        } else {
            self.preset_index - 1
        };
        self.load_preset(prev);
    }

    pub fn toggle_ab(&mut self) {
        self.ab.current().clone_into(&mut self.params);
        self.ab.toggle();
        self.params = self.ab.current().clone();
    }

    pub fn snapshot_ab(&mut self) {
        self.ab.snapshot_to_inactive();
    }

    pub fn update_position(&mut self, position: OrbPosition) {
        self.params.position = position;
        self.params.position.clamp();
    }

    pub fn sync_to_ab(&mut self) {
        match self.ab.active {
            'A' => self.ab.slot_a = self.params.clone(),
            'B' => self.ab.slot_b = self.params.clone(),
            _ => {}
        }
    }

    pub fn panic(&mut self) {
        self.params = AllParams::default();
        self.preset_index = 0;
    }

    pub fn randomize(&mut self) {
        use rand::Rng;
        let mut rng = rand::thread_rng();
        self.params.position.azimuth = rng.gen_range(-180.0..180.0);
        self.params.position.elevation = rng.gen_range(-90.0..90.0);
        self.params.position.distance = rng.gen_range(0.3..3.0);
        self.params.room_amount = rng.gen_range(0.0..1.0);
        self.params.mix = rng.gen_range(0.5..1.0);
        self.params.externalization = rng.gen_range(0.0..1.0);
        self.params.sub_width = rng.gen_range(0.0..2.0);
        self.params.low_width = rng.gen_range(0.0..2.0);
        self.params.mid_width = rng.gen_range(0.0..2.0);
        self.params.high_width = rng.gen_range(0.0..2.0);
        self.params.bass_mono = rng.gen_bool(0.3);
        self.params.split_spatial = rng.gen_bool(0.5);
        self.params.genre = Genre::ALL[rng.gen_range(0..Genre::ALL.len())];
        self.params.source_type = SourceType::ALL[rng.gen_range(0..SourceType::ALL.len())];
        self.params.depth_zone = DepthZone::ALL[rng.gen_range(0..DepthZone::ALL.len())];
        self.params.output_mode = OutputMode::ALL[rng.gen_range(0..OutputMode::ALL.len())];
        self.params.room = RoomModel::all()[rng.gen_range(0..RoomModel::all().len())];
    }

    pub fn save_preset_to_file(&self, name: &str) -> Result<String, String> {
        let dir = dirs::config_dir()
            .ok_or("Cannot find config dir")?
            .join("StereoEblet3D")
            .join("presets");
        std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
        
        let path = dir.join(format!("{}.json", name));
        let json = serde_json::to_string_pretty(&self.params).map_err(|e| e.to_string())?;
        std::fs::write(&path, json).map_err(|e| e.to_string())?;
        
        Ok(path.display().to_string())
    }

    pub fn load_preset_from_file(&mut self, name: &str) -> Result<(), String> {
        let path = dirs::config_dir()
            .ok_or("Cannot find config dir")?
            .join("StereoEblet3D")
            .join("presets")
            .join(format!("{}.json", name));
        
        let json = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
        self.params = serde_json::from_str(&json).map_err(|e| e.to_string())?;
        
        Ok(())
    }

    pub fn list_saved_presets(&self) -> Vec<String> {
        let dir = match dirs::config_dir() {
            Some(d) => d.join("StereoEblet3D").join("presets"),
            None => return vec![],
        };
        
        match std::fs::read_dir(&dir) {
            Ok(entries) => entries
                .filter_map(|e| e.ok())
                .filter_map(|e| {
                    let path = e.path();
                    if path.extension().map(|ext| ext == "json").unwrap_or(false) {
                        path.file_stem().and_then(|s| s.to_str()).map(|s| s.to_string())
                    } else {
                        None
                    }
                })
                .collect(),
            Err(_) => vec![],
        }
    }
}

impl Default for GuiState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_orb_position_clamp() {
        let mut pos = OrbPosition::new(100.0, -60.0, 5.0);
        pos.clamp();
        assert_eq!(pos.azimuth, 90.0);
        assert_eq!(pos.elevation, -45.0);
        assert_eq!(pos.distance, 3.0);
    }

    #[test]
    fn test_head_trajectory_range() {
        let low = OrbPosition::new(0.0, -45.0, 1.0);
        let high = OrbPosition::new(0.0, 90.0, 1.0);
        assert!((low.head_trajectory() - 0.0).abs() < 0.01);
        assert!((high.head_trajectory() - 1.0).abs() < 0.01);
    }

    #[test]
    fn test_preset_loading() {
        let mut state = GuiState::new();
        state.load_preset(0);
        assert_eq!(state.params.position.azimuth, 0.0);
        assert_eq!(state.params.position.elevation, -15.0);
        assert!(state.params.bass_mono);
    }

    #[test]
    fn test_ab_toggle() {
        let mut state = GuiState::new();
        state.load_preset(0);
        state.sync_to_ab();
        assert_eq!(state.ab.active, 'A');
        state.toggle_ab();
        assert_eq!(state.ab.active, 'B');
        state.toggle_ab();
        assert_eq!(state.ab.active, 'A');
    }

    #[test]
    fn test_room_model_from_index() {
        assert_eq!(RoomModel::from_index(0), RoomModel::Dry);
        assert_eq!(RoomModel::from_index(4), RoomModel::Cathedral);
        assert_eq!(RoomModel::from_index(99), RoomModel::Studio);
    }
}
