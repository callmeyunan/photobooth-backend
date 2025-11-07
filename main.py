import io
import os
import re
import json
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import face_recognition

# ==============================
# Konfigurasi
# ==============================

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# DOMAIN frontend kamu, ganti nanti:
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app = FastAPI(title="Photobooth Face Search (Google Drive, Render.com)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_drive_service():
    """Inisialisasi Google Drive client dari environment variable.

    Harus ada env:
    - GOOGLE_SERVICE_ACCOUNT_JSON = isi file JSON service account (string)
    """
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise RuntimeError("Environment variable GOOGLE_SERVICE_ACCOUNT_JSON belum di-set")

    info = json.loads(sa_json)
    credentials = service_account.Credentials.from_service_account_info(
        info, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=credentials)
    return service


def extract_folder_id(folder_url_or_id: str) -> str:
    """Terima folder ID langsung atau URL Google Drive dan kembalikan folder ID-nya."""
    if not folder_url_or_id.startswith("http"):
        return folder_url_or_id

    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", folder_url_or_id)
    if not m:
        raise ValueError("Tidak bisa membaca folder ID dari URL")
    return m.group(1)


def list_image_files_in_folder(service, folder_or_file_id: str) -> List[dict]:
    # Kalau ID-nya file, langsung return satu elemen
    try:
        file = service.files().get(fileId=folder_or_file_id, fields="id, name, mimeType").execute()
        if file["mimeType"].startswith("image/"):
            return [file]
    except Exception:
        pass

    # Kalau bukan file, baru anggap folder
    query = (
        f"'{folder_or_file_id}' in parents and "
        "mimeType contains 'image/' and "
        "trashed = false"
    )
    fields = "files(id, name, mimeType)"
    results = service.files().list(q=query, fields=fields).execute()
    return results.get("files", [])


def download_image_bytes(service, file_id: str) -> bytes:
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh.read()


def make_view_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?id={file_id}"


def make_thumb_url(file_id: str) -> str:
    return f"https://drive.google.com/thumbnail?id={file_id}"


def compute_face_embedding_from_bytes(image_bytes: bytes) -> Optional[list]:
    """Hitung embedding wajah dari bytes gambar. Ambil wajah pertama saja."""
    image = face_recognition.load_image_file(io.BytesIO(image_bytes))
    locations = face_recognition.face_locations(image)
    if not locations:
        return None
    encodings = face_recognition.face_encodings(image, known_face_locations=locations)
    if not encodings:
        return None
    return encodings[0]


@app.post("/face-search")
async def face_search(
    file: UploadFile = File(...),
    folder: str = Form(..., description="Google Drive folder URL atau ID"),
):
    """Terima foto wajah + folder Drive, kembalikan foto-foto yang cocok."""
    try:
        folder_id = extract_folder_id(folder)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1. Baca bytes dari upload
    user_image_bytes = await file.read()

    # 2. Hitung embedding wajah user
    user_embedding = compute_face_embedding_from_bytes(user_image_bytes)
    if user_embedding is None:
        return JSONResponse({"matches": []})

    # 3. Inisialisasi Google Drive
    service = get_drive_service()

    # 4. List file image di folder
    files = list_image_files_in_folder(service, folder_id)
    if not files:
        return JSONResponse({"matches": []})

    from face_recognition.api import face_distance

    THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.6"))

    matches = []

    # 5. Loop setiap gambar di folder untuk dicek
    for f in files:
        file_id = f["id"]
        try:
            img_bytes = download_image_bytes(service, file_id)
        except Exception as e:
            print(f"Gagal download file {file_id}: {e}")
            continue

        embedding = compute_face_embedding_from_bytes(img_bytes)
        if embedding is None:
            continue

        dist = face_distance([user_embedding], embedding)[0]
        if dist <= THRESHOLD:
            matches.append(
                {
                    "photo_id": file_id,
                    "drive_view_url": make_view_url(file_id),
                    "drive_thumb_url": make_thumb_url(file_id),
                    "captured_at": None,
                    "distance": float(dist),
                }
            )

    # 6. Urutkan dari yang paling mirip (jarak terkecil)
    matches.sort(key=lambda m: m["distance"])

    # 7. Hapus 'distance' sebelum dikirim ke frontend
    for m in matches:
        m.pop("distance", None)

    return JSONResponse({"matches": matches})


@app.get("/")
def root():
    return {"status": "ok", "message": "Photobooth face-search backend (Render.com)"}
