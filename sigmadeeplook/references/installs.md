# What a missing install costs, and its install line

Every row below is a 'Not looked at' row when the tool is absent. Nothing needs to be installed for the look to run; install only what the human approves. `python scripts/look.py doctor` shows which of these this machine has.

| name | kind | what it adds | install |
|---|---|---|---|
| ffmpeg | tool | video and audio: loudness, black/freeze/silence, scenes, sheets, subtitles | winget install Gyan.FFmpeg |
| ffprobe | tool | codec and stream facts | winget install Gyan.FFmpeg |
| pdftotext | tool | PDF text (PyMuPDF also does it) | winget install oschwartz10612.Poppler |
| pdftoppm | tool | PDF page pictures (PyMuPDF also does it) | winget install oschwartz10612.Poppler |
| soffice | tool | recalculated xlsx values, rendered Office pages | winget install TheDocumentFoundation.LibreOffice |
| tesseract | tool | OCR of scanned pages and images | winget install UB-Mannheim.TesseractOCR |
| exiftool | tool | full EXIF, XMP and maker notes | winget install OliverBetz.ExifTool |
| pandoc | tool | document conversion for odd formats | winget install JohnMacFarlane.Pandoc |
| 7z | tool | 7z, rar, iso and cab member listing and screening | winget install 7zip.7zip |
| ctags | tool | function index of source files | winget install UniversalCtags.Ctags |
| git | tool | git bundle commit statistics | winget install Git.Git |
| chrome | tool | screenshots of web pages | winget install Google.Chrome |
| blender | tool | fbx and blend contents | winget install BlenderFoundation.Blender |
| diec | tool | packer, compiler and linker identification | download Detect It Easy 3.21 portable from github.com/horsicq/DIE-engine/releases (25 MB), put diec.exe on PATH |
| capa | tool | capabilities of a binary (ATT&CK-mapped) | download capa-v10.0.0 standalone from github.com/mandiant/capa/releases (~46 MB), put capa.exe on PATH |
| floss | tool | strings a program hides until it runs | download floss-v3.2.0 standalone from github.com/mandiant/flare-floss/releases (~44 MB), put floss.exe on PATH |
| gltf-validator | tool | glTF specification validation | npm install -g gltf-validator (~2 MB) |
| openssl | tool | certificate fields when cryptography is absent | winget install ShiningLight.OpenSSL.Light |
| ghidra | tool | decompiled functions (--func on a binary) | Ghidra 12.1.4 + JDK 25 (about 760 MB): see references/binary.md |
| PIL | python package | pictures, sheets, thumbnails | pip install pillow |
| numpy | python package | image and audio maths | pip install numpy |
| pypdf | python package | PDF text fallback | pip install pypdf |
| fitz | python package | PDF text, pages, outline, tables, hidden-text checks | pip install pymupdf |
| openpyxl | python package | xlsx --sheet/--range | pip install openpyxl |
| fontTools | python package | font tables and glyph coverage | pip install fonttools |
| trafilatura | python package | web page main text | pip install trafilatura |
| duckdb | python package | --sql on csv, parquet, jsonl; fast profiles | pip install duckdb |
| pyarrow | python package | parquet and arrow | pip install pyarrow |
| faster_whisper | python package | speech to text | pip install faster-whisper |
| librosa | python package | tempo and key of music | pip install librosa |
| scenedetect | python package | (reserved) alternative cut detector | pip install scenedetect[opencv] |
| defusedxml | python package | safe XML parsing | pip install defusedxml |
| brotli | python package | woff2 fonts | pip install brotli |
| docx | python package | (not needed: Word is read as XML) | pip install python-docx |
| pptx | python package | (not needed: PowerPoint is read as XML) | pip install python-pptx |
| pefile | python package | PE resources, Rich header, checksum | pip install pefile |
| extract_msg | python package | Outlook .msg bodies and attachments | pip install extract-msg |
| lxml | python package | faster XML | pip install lxml |
| cairosvg | python package | rendering svg | pip install cairosvg |
| rapidocr_onnxruntime | python package | OCR of video frames, images, scanned pages | pip install rapidocr-onnxruntime |
| lief | python package | real Authenticode verification (chain and hash), imphash | pip install lief |
| oletools | python package | VBA macro source, auto-run routines, suspicious calls | pip install oletools |
| python_calamine | python package | very large xlsx files | pip install python-calamine |
| dnfile | python package | .NET assembly names, references, types | pip install dnfile |
| pymupdf4llm | python package | (reserved) PDF to markdown with tables | pip install pymupdf4llm |
| trimesh | python package | mesh watertight, volume, bodies | pip install trimesh |
| pysubs2 | python package | (not needed: subtitles are parsed with the standard library) | pip install pysubs2 |
| icalendar | python package | exact recurrence rules and daylight-saving transitions | pip install icalendar recurring-ical-events |
| recurring_ical_events | python package | exact recurrence expansion | pip install recurring-ical-events |
| magika | python package | second opinion on the file type | pip install magika |
| msoffcrypto | python package | (reserved) encrypted Office files, with a password | pip install msoffcrypto-tool |
| cryptography | python package | certificate and signer fields | pip install cryptography |
| rapidfuzz | python package | fast near-duplicate removal | pip install rapidfuzz |
| cv2 | python package | faces (YuNet) and image maths | pip install opencv-python |
| fastavro | python package | Avro record values | pip install fastavro |
| Evtx | python package | Windows event ids, providers and messages | pip install python-evtx |
| pyannote | python package | speaker turns (also needs the model) | accept the model terms on huggingface.co/pyannote/speaker-diarization-community-1 once, then cache it (~35 MB) |
| transformers | python package | sound-event labels (also needs the AST model) | pip install transformers |
| psd_tools | python package | Photoshop layers, hidden layers, text layers | pip install psd-tools |
| onnx | python package | (reserved) ONNX operator detail | pip install onnx |
| ast | model | sound-event labels (speech, music, applause, siren) | download MIT/ast-finetuned-audioset-10-10-0.4593 from Hugging Face once (~345 MB, ungated) |
| yunet | model | faces in video frames and images | download face_detection_yunet_2023mar.onnx from github.com/opencv/opencv_zoo (0.23 MB) |
| pyannote | model | speaker turns (also needs the model) | accept the model terms on huggingface.co/pyannote/speaker-diarization-community-1 once, then cache it (~35 MB) |
