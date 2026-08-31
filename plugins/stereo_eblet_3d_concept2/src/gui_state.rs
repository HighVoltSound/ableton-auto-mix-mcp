use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum RoomModel {
    Dry,
    Booth,
    Studio,
    Club,
    Cathedral,
}

impl RoomModel {
    pub fn all() -> [RoomModel; 5] {
        [
            RoomModel::Dry,
            RoomModel::Booth,
            RoomModel::Studio,
            RoomModel::Club,
            RoomModel::Cathedral,
        ]
    }

    pub fn label(&self) -> &'static str {
        match self {
            RoomModel::Dry => "DRY",
            RoomModel::Booth => "BOOTH",
            RoomModel::Studio => "STUDIO",
            RoomModel::Club => "CLUB",
            RoomModel::Cathedral => "CATH",
        }
    }

    pub fn to_index(&self) -> i32 {
        *self as i32
    }

    pub fn from_index(index: i32) -> Self {
        match index {
            1 => RoomModel::Booth,
            2 => RoomModel::Studio,
            3 => RoomModel::Club,
            4 => RoomModel::Cathedral,
            _ => RoomModel::Dry,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrbPosition {
    pub azimuth: f32,
    pub elevation: f32,
    pub distance: f32,
}

impl OrbPosition {
    pub fn head_trajectory(&self) -> f32 {
        let el_norm = (self.elevation.max(0.0) / 90.0).clamp(0.0, 1.0);
        let dist_norm = ((self.distance - 0.3) / 2.7).clamp(0.0, 1.0);
        (el_norm * 0.4 + dist_norm * 0.6).clamp(0.0, 1.0)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllParams {
    pub position: OrbPosition,
    pub split_spatial: i32, // 0 = Off, 1 = Mid, 2 = Wide
    pub room: RoomModel,
    pub room_amount: f32,
    pub mix: f32,
    pub club_safe: bool,
}

impl Default for AllParams {
    fn default() -> Self {
        Self {
            position: OrbPosition {
                azimuth: 0.0,
                elevation: 0.0,
                distance: 1.0,
            },
            split_spatial: 1,
            room: RoomModel::Studio,
            room_amount: 0.2,
            mix: 1.0,
            club_safe: false,
        }
    }
}

pub struct ABState {
    pub active: char,
    pub state_a: AllParams,
    pub state_b: AllParams,
}

impl Default for ABState {
    fn default() -> Self {
        Self {
            active: 'A',
            state_a: AllParams::default(),
            state_b: AllParams::default(),
        }
    }
}

pub struct GuiState {
    pub params: AllParams,
    pub ab: ABState,
    pub preset_index: usize,
    pub bypassed: bool,
}

impl GuiState {
    pub fn new() -> Self {
        Self {
            params: AllParams::default(),
            ab: ABState::default(),
            preset_index: 0,
            bypassed: false,
        }
    }

    pub fn load_preset(&mut self, index: usize) {
        if index < PRESETS.len() {
            let p = &PRESETS[index];
            self.params.position = p.position.clone();
            self.params.split_spatial = p.split_spatial;
            self.params.room = p.room;
            self.params.room_amount = p.room_amount;
            self.params.mix = p.mix;
            self.params.club_safe = p.club_safe;
            self.preset_index = index;
        }
    }

    pub fn toggle_ab(&mut self) {
        if self.ab.active == 'A' {
            self.ab.state_a = self.params.clone();
            self.params = self.ab.state_b.clone();
            self.ab.active = 'B';
        } else {
            self.ab.state_b = self.params.clone();
            self.params = self.ab.state_a.clone();
            self.ab.active = 'A';
        }
    }

    pub fn next_preset(&mut self) {
        let mut idx = self.preset_index + 1;
        if idx >= PRESETS.len() {
            idx = 0;
        }
        self.load_preset(idx);
    }

    pub fn prev_preset(&mut self) {
        let mut idx = self.preset_index;
        if idx == 0 {
            idx = PRESETS.len() - 1;
        } else {
            idx -= 1;
        }
        self.load_preset(idx);
    }
}

impl Default for GuiState {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone)]
pub struct Preset {
    pub name: &'static str,
    pub position: OrbPosition,
    pub split_spatial: i32,
    pub room: RoomModel,
    pub room_amount: f32,
    pub mix: f32,
    pub club_safe: bool,
}

impl Preset {
    pub const fn new(
        name: &'static str,
        azimuth: f32,
        elevation: f32,
        distance: f32,
        split_spatial: i32,
        room: RoomModel,
        room_amount: f32,
        mix: f32,
        club_safe: bool,
    ) -> Self {
        Self {
            name,
            position: OrbPosition {
                azimuth,
                elevation,
                distance,
            },
            split_spatial,
            room,
            room_amount,
            mix,
            club_safe,
        }
    }
}

pub const PRESETS: &[Preset] = &[
    Preset::new("INIT", 0.0, 0.0, 1.0, 1, RoomModel::Dry, 0.0, 1.0, false),
    Preset::new("TECHNO KICK / SUB", 0.0, 0.0, 0.5, 0, RoomModel::Dry, 0.0, 1.0, true),
    Preset::new("DNB BASS", 0.0, -10.0, 0.7, 1, RoomModel::Booth, 0.1, 1.0, true),
    Preset::new("HOUSE CLAP", 0.0, 15.0, 0.8, 1, RoomModel::Studio, 0.20, 1.0, false),
    Preset::new("TRAP HAT", 20.0, 10.0, 0.6, 1, RoomModel::Dry, 0.05, 1.0, false),
    Preset::new("LEAD", 15.0, 15.0, 0.8, 1, RoomModel::Studio, 0.25, 1.0, false),
    Preset::new("ATMOSPHERIC PAD", -60.0, 65.0, 2.5, 2, RoomModel::Cathedral, 0.50, 1.0, false),
    Preset::new("PSY FX WIDE", 75.0, 75.0, 2.0, 2, RoomModel::Club, 0.45, 1.0, false),
];
