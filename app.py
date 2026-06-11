import re
from typing import Iterable

import requests
import streamlit as st
from pypdf import PdfReader


st.set_page_config(page_title="PDF File Reader", page_icon="📄", layout="centered")

st.title("📄 PDF File Reader")
st.write("----------------")

openai_key = st.text_input("OPENAI_API_KEY", type="password")
uploaded_file = st.file_uploader("PDF 파일을 올려주세요", type=["pdf"])
st.write("----------------")


def extract_pdf_text(uploaded_pdf) -> str:
    reader = PdfReader(uploaded_pdf)
    pages: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[{page_number}페이지]\n{text.strip()}")
    return "\n\n".join(pages)


def split_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    clean_text = re.sub(r"\s+", " ", text).strip()
    if not clean_text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(clean_text):
        end = min(start + chunk_size, len(clean_text))
        chunks.append(clean_text[start:end])
        if end == len(clean_text):
            break
        start = max(0, end - overlap)
    return chunks


def keyword_terms(question: str) -> list[str]:
    terms = re.findall(r"[가-힣A-Za-z0-9]{2,}", question.lower())
    return list(dict.fromkeys(terms))


def select_context(chunks: Iterable[str], question: str, limit: int = 4) -> str:
    terms = keyword_terms(question)
    scored: list[tuple[int, str]] = []
    for chunk in chunks:
        lower_chunk = chunk.lower()
        score = sum(lower_chunk.count(term) for term in terms)
        scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [chunk for score, chunk in scored[:limit] if score > 0]
    if not selected:
        selected = [chunk for _, chunk in scored[:limit]]
    return "\n\n".join(selected)


def ask_openai(api_key: str, question: str, context: str) -> str:
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4.1-mini",
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": "PDF 내용만 근거로 한국어로 답하세요. 근거가 부족하면 부족하다고 말하세요.",
                },
                {
                    "role": "user",
                    "content": f"질문: {question}\n\nPDF 내용:\n{context}",
                },
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


if uploaded_file is not None:
    if not openai_key.strip():
        st.info("OPENAI_API_KEY를 입력한 뒤 PDF를 분석할 수 있습니다.")
        st.stop()

    pdf_text = extract_pdf_text(uploaded_file)
    if not pdf_text:
        st.error("PDF에서 텍스트를 추출하지 못했습니다.")
        st.stop()

    chunks = split_text(pdf_text)
    st.success(f"PDF 텍스트 추출 완료: {len(chunks)}개 문단")

    st.header("PDF에게 질문하세요")
    question = st.text_input("질문 입력")

    if st.button("질문하기"):
        if question.strip() == "":
            st.warning("질문을 입력하세요")
        else:
            with st.spinner("답변 생성중...", show_time=True):
                try:
                    context = select_context(chunks, question)
                    answer = ask_openai(openai_key.strip(), question.strip(), context)
                    st.markdown(answer)
                except requests.HTTPError as exc:
                    st.error(f"OpenAI API 오류가 발생했습니다: {exc.response.text}")
                except Exception as exc:
                    st.error(f"답변 생성 중 오류가 발생했습니다: {exc}")
