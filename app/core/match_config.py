from datetime import timedelta

# --------------------------------------------------
# STATIONARY ACTIVATION
# --------------------------------------------------

# How long user must be stationary before becoming eligible
STATIONARY_THRESHOLD_SECONDS = 15   # 🔥 change to 15 for testing

# --------------------------------------------------
# PRESENCE
# --------------------------------------------------

# How long presence remains valid
PRESENCE_EXPIRY_MINUTES = 5

# --------------------------------------------------
# MATCHING
# --------------------------------------------------

DEFAULT_RADIUS_METERS = 300

# --------------------------------------------------
# VENUE-SPECIFIC DELAYS
# --------------------------------------------------

GYM_DELAY_MINUTES = 70
YOGA_DELAY_MINUTES = 70

# --------------------------------------------------
# AUTO-NUDGE BEHAVIOR
# --------------------------------------------------

AUTO_NUDGE_ENABLED = True

# --------------------------------------------------
# DEBUG MODE
# --------------------------------------------------

DEBUG_MATCH_LOGS = True
