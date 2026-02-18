from enum import Enum

class OnboardingStep(str, Enum):
    location = "location"
    prefs = "prefs"
    intent = "intent"
    lifestyle = "lifestyle"
    media = "media"
    note = "note"
    done = "done"

class WingmanStyle(str, Enum):
    wingwoman = "wingwoman"
    wingman = "wingman"

class HeightPreference(str, Enum):
    shorter = "shorter"
    taller = "taller"
    same = "same"
    any = "any"

class IntentType(str, Enum):
    casual = "casual"
    dating = "dating"
    relationship = "relationship"

class LocationPermission(str, Enum):
    none = "none"
    coarse = "coarse"
    fine = "fine"
