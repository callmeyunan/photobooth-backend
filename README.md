# Photobooth Face Search Backend (Render.com)

Backend FastAPI untuk sistem photobooth:
- menerima foto wajah (upload)
- menerima folder Google Drive (URL atau ID)
- scan semua foto di folder tersebut
- mencari wajah yang mirip menggunakan `face_recognition`
- mengembalikan URL foto-foto dari Google Drive untuk ditampilkan di frontend (Vercel dll.)

Dirancang agar mudah dideploy di **Render.com** menggunakan Docker.

## Struktur

- `main.py` — aplikasi FastAPI
- `requirements.txt` — dependency Python
- `Dockerfile` — image definition untuk Render (env: docker)
- `render.yaml` — contoh konfigurasi Render (opsional)
- (TIDAK ADA) `service_account.json` — diganti dengan env var

## Konfigurasi Google Drive (Service Account)

1. Buat project di Google Cloud.
2. Aktifkan **Google Drive API**.
3. Buat **Service Account** dan download file JSON-nya.
4. Buka file JSON tersebut dan copy seluruh isinya.
5. Di Render, saat membuat service:
   - Tambahkan Environment Variable:
     - **Key**: `GOOGLE_SERVICE_ACCOUNT_JSON`
     - **Value**: paste isi file JSON tadi (format JSON utuh).

Backend akan meng-parse JSON ini dari environment, jadi kamu **tidak perlu** meng-upload file ke server.

## Endpoint Utama

### `POST /face-search`

Form-data:

- `file`: image/jpeg — foto wajah user (snapshot dari kamera)
- `folder`: string — ID folder Google Drive atau URL folder

Response:

```json
{
  "matches": [
    {
      "photo_id": "1AbCdEfGhIJ",
      "drive_view_url": "https://drive.google.com/uc?id=1AbCdEfGhIJ",
      "drive_thumb_url": "https://drive.google.com/thumbnail?id=1AbCdEfGhIJ",
      "captured_at": null
    }
  ]
}
```

Jika tidak ada wajah atau tidak ada match, `matches` akan berupa array kosong.

## Environment Variables Penting

- `GOOGLE_SERVICE_ACCOUNT_JSON` (WAJIB)  
  Isi file JSON Service Account Google Drive.

- `ALLOWED_ORIGINS` (opsional, default: `*`)  
  Comma-separated list domain frontend yang diizinkan untuk CORS.  
  Contoh:
  ```text
  https://photos.nineties.id,https://your-vercel-domain.vercel.app
  ```

- `FACE_MATCH_THRESHOLD` (opsional, default: `0.6`)  
  Makin kecil nilai, makin ketat pencocokannya.

## Deploy ke Render (Langkah Singkat)

1. Buat repo dari folder ini (GitHub/GitLab).
2. Di Render.com:
   - Klik **New +** → **Web Service**.
   - Pilih repo backend ini.
   - Environment: pilih **Docker**.
   - Render otomatis baca `Dockerfile`.
3. Setelah service dibuat:
   - Di tab **Environment**, tambahkan:
     - `GOOGLE_SERVICE_ACCOUNT_JSON` → paste isi file JSON SA.
     - `ALLOWED_ORIGINS` → domain frontend kamu.
4. Deploy. Setelah live, kamu akan mendapat URL, misal:
   - `https://photobooth-backend.onrender.com`
5. Di frontend (Vercel), set:
   ```js
   const API_BASE = "https://photobooth-backend.onrender.com";
   ```

## Jalankan Lokal (Opsional)

```bash
pip install -r requirements.txt
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "...", ...}'  # isi JSON SA
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Lalu test:

- `POST http://localhost:8000/face-search`
- Form-data: `file` (image), `folder` (ID/URL folder Drive).
