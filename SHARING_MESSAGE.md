# Message Template for Sharing

## Option 1: Formal (Bahasa Melayu)

Assalamualaikum w.b.t.

Saya telah membina sebuah aplikasi web kecil untuk menjana pasangan Soal-Jawab (Q&A) secara automatik daripada fail teks Bahasa Melayu.

Aplikasi ini menggunakan sistem tiga peringkat (three-stage AI pipeline):

1. **Pre-filter (Penyaring Awal)**: Menapis dan menolak chunk teks yang mengandungi metadata (nama fail, penulis, jurnal), maklumat sistem, atau kandungan yang tidak sesuai sebelum proses penjanaan.

2. **Generator (Penjana)**: Menjana sehingga 10 pasangan Q&A untuk setiap chunk teks yang sah. Setiap pasangan dijana dalam Bahasa Melayu baku dan merangkumi pelbagai tahap kesukaran (fakta → analitikal).

3. **Reviewer (Penyemak)**: Menyemak setiap pasangan Q&A yang dijana, menapis sebarang metadata yang terlepas (seperti nama penulis, e-mel, jurnal, rujukan), dan memastikan setiap soalan dan jawapan disokong oleh teks sumber.

**Aliran kerja:**
```
Input Text → [Pre-filter] → Chunks Bersih → [Generator] → Q&A Candidates → [Reviewer] → Q&A Final → CSV
```

Ciri-ciri utama:
- Antara muka web yang mudah digunakan
- Pemprosesan selari untuk kelajuan
- Penapisan metadata automatik
- Eksport ke CSV
- Memproses fail dengan format metadata (ID Fail, Tajuk, Penulis, dll)

Link repository: https://github.com/zuftt/qna-pair-generator

Sesiapa yang berminat boleh cuba! Terima kasih.

---

## Option 2: Casual (Bahasa Melayu)

Assalamualaikum!

Baru siap buat small project untuk generate Q&A pairs dari text file. Workflow dia ada 3 stage:

**Stage 1 (Pre-filter)**: Filter out metadata, system info, dan content yang tak sesuai sebelum generate

**Stage 2 (Generator)**: Generate Q&A pairs dari clean text chunks - sampai 10 pairs per chunk

**Stage 3 (Reviewer)**: Review setiap pair, reject kalau ada metadata terlepas (penulis, jurnal, e-mel, etc), ensure quality

Flow: Text → Filter → Generate → Review → CSV output

Ada web UI, boleh process files dengan cepat, dan export as CSV. Perfect untuk buat study materials atau training datasets dari text Bahasa Melayu.

Boleh tengok kat: https://github.com/zuftt/qna-pair-generator

Kalau ada yang nak try, welcome! 🙏

---

## Option 3: English (Professional)

Assalamualaikum,

I've developed a small web application that automatically generates high-quality Question-Answer pairs in Bahasa Melayu from text files.

The system uses a three-stage AI pipeline to ensure quality:

**Stage 1 (Pre-filter)**: Filters out text chunks containing metadata (file info, author names), system information, or inappropriate content before processing.

**Stage 2 (Generator)**: Generates up to 10 Q&A pairs per validated text chunk. Each pair is created in standard Bahasa Melayu across various difficulty levels (factual → analytical).

**Stage 3 (Reviewer)**: Reviews each generated Q&A pair, filters out any metadata that slipped through (author names, journals, emails, references), and ensures questions and answers are supported by source text.

**Workflow:**
```
Input Text → [Pre-filter] → Clean Chunks → [Generator] → Q&A Candidates → [Reviewer] → Final Q&A → CSV Export
```

Features:
- User-friendly web interface
- Parallel processing for speed
- Automatic metadata filtering
- CSV export
- Handles files with metadata headers

Repository: https://github.com/zuftt/qna-pair-generator

Feel free to try it out! Feedback welcome.

