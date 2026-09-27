import os
from dotenv import load_dotenv

# Load settings from a local .env file (never commit real secrets)
load_dotenv()

# MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "neurolens")

# JWT authentication
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Account creation
ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true").lower() == "true"
DEFAULT_USER_ROLE = os.getenv("DEFAULT_USER_ROLE", "clinician")

# Optional: administrator account created at start-up if it does not exist yet
FIRST_ADMIN_EMAIL = os.getenv("FIRST_ADMIN_EMAIL", "").strip().lower()
FIRST_ADMIN_PASSWORD = os.getenv("FIRST_ADMIN_PASSWORD", "")
FIRST_ADMIN_NAME = os.getenv("FIRST_ADMIN_NAME", "Administrator").strip() or "Administrator"

# CORS: comma-separated list of frontend origins allowed to call the API
# (not needed when the dashboard is served by this app from the same URL)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:4200").split(",") if o.strip()]

# --- Model (downloaded from Hugging Face Hub at start-up) ---
REPO_ID = os.getenv("HF_REPO_ID", "Bharathikannan/thyroid-cancer-detection")
MODEL_FILENAME = os.getenv("HF_MODEL_FILENAME", "thyroid_cancer_model.keras")
HF_REVISION = os.getenv("HF_REVISION") or None          # pin a commit for reproducible deployments
HF_TOKEN = os.getenv("HF_TOKEN") or None                # only needed for a private repository
# Used when Hugging Face is unreachable (local development)
LOCAL_MODEL_PATH = os.getenv("LOCAL_MODEL_PATH", os.path.join("model_artifacts", MODEL_FILENAME))
MODEL_DISPLAY_NAME = os.getenv("MODEL_DISPLAY_NAME", "Fibonacci-Net")

# Class names in the model's output order.
#   Current model (thyroid, 1 sigmoid output):  CLASS_NAMES=benign,malignant
#   Brain tumor model (4 softmax outputs):      CLASS_NAMES=glioma,meningioma,notumor,pituitary
CLASS_NAMES = [c.strip() for c in os.getenv("CLASS_NAMES", "benign,malignant").split(",") if c.strip()]
_DEFAULT_LABELS = {
    "glioma": "Glioma", "meningioma": "Meningioma", "notumor": "No tumor", "pituitary": "Pituitary tumor",
    "benign": "Benign", "malignant": "Malignant",
}
CLASS_LABELS = {c: _DEFAULT_LABELS.get(c, c.replace("_", " ").capitalize()) for c in CLASS_NAMES}

# Model input — must match the training notebook
IMG_SIZE = (224, 224)

# Built Angular dashboard (served by this app when the folder exists, e.g. inside the Docker image)
STATIC_DIR = os.getenv("STATIC_DIR", "static")
