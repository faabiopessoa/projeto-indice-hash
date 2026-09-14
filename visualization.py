from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st


def load_styles():
    style_path = Path(__file__).with_name("styles.css")
    styles = style_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{styles}</style>", unsafe_allow_html=True)


def format_number(value):
    return f"{value:,}".replace(",", ".")


def format_decimal(value, decimal_places=2):
    formatted = f"{value:,.{decimal_places}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_time(milliseconds):
    decimal_places = 6 if milliseconds < 0.001 else 4
    return f"{format_decimal(milliseconds, decimal_places)} ms"


def render_header(index_ready, file_name):
    status = "Aguardando dados"

    if index_ready:
        status = f"Índice construído · {escape(file_name)}"

    st.markdown(
        f"""
        <div class="app-header">
            <div>
                <h1>Índice HASH Estático</h1>
                <p>Simulação de páginas, buckets, overflow e custo de busca</p>
            </div>
            <div class="status-pill">{status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_intro(text):
    st.markdown(
        f'<p class="section-note">{escape(text)}</p>',
        unsafe_allow_html=True,
    )


def show_metrics(items):
    columns = st.columns(len(items))

    for column, (label, value) in zip(columns, items):
        column.metric(label, value)


def make_page_dataframe(page, start=0, stop=None):
    return pd.DataFrame(
        [
            {"Posição na página": position, "Registro": record}
            for position, record in enumerate(page[start:stop], start=start)
        ]
    )


def make_bucket_dataframe(entries, capacity=None):
    rows = []
    row_count = len(entries) if capacity is None else capacity

    for position in range(row_count):
        if position < len(entries):
            key, page_id = entries[position]
            rows.append(
                {
                    "Posição": position,
                    "Chave": key,
                    "page_id": format_number(page_id),
                }
            )
        else:
            rows.append(
                {
                    "Posição": position,
                    "Chave": "— espaço livre —",
                    "page_id": "—",
                }
            )

    return pd.DataFrame(rows)


def highlight_record(dataframe, key, column_name):
    if key is None or dataframe.empty:
        return dataframe

    def highlight_row(row):
        if row[column_name] == key:
            style = "background-color: #bbf7d0; color: #14532d; font-weight: 700;"
            return [style] * len(row)

        return [""] * len(row)

    return dataframe.style.apply(highlight_row, axis=1)


def show_dataframe(dataframe, height=250, highlighted_key=None, key_column=None):
    displayed_data = dataframe

    if highlighted_key is not None and key_column is not None:
        displayed_data = highlight_record(dataframe, highlighted_key, key_column)

    st.dataframe(
        displayed_data,
        hide_index=True,
        width="stretch",
        height=height,
    )


def render_page_preview(pages, page_id):
    page = pages[page_id]
    st.markdown(f"#### Página {format_number(page_id)}")
    st.caption(f"{format_number(len(page))} registros · exibindo os primeiros 5")
    show_dataframe(make_page_dataframe(page, stop=5), height=220)


def render_hash_flow(result, nb):
    if result["location"] == "primary":
        area_text = f"Principal · posição {result['bucket_position']}"
        area_tone = "hash"
    elif result["location"] == "overflow":
        area_text = f"Overflow · posição {result['bucket_position']}"
        area_tone = "overflow"
    else:
        area_text = "Principal + overflow"
        area_tone = "normal"

    page_text = "Não acessada"
    if result["page_id"] is not None:
        page_text = f"Página {format_number(result['page_id'])}"

    result_text = "Encontrada" if result["found"] else "Não encontrada"
    result_tone = "success" if result["found"] else "error"
    steps = [
        ("1 · Chave", result["key"], "normal"),
        ("2 · custom_hash", f"h(chave, {format_number(nb)})", "hash"),
        ("3 · Endereço", f"Bucket {format_number(result['bucket_index'])}", "hash"),
        ("4 · Área consultada", area_text, area_tone),
        ("5 · page_id", page_text, "hash" if result["page_id"] is not None else "normal"),
        ("6 · Resultado", result_text, result_tone),
    ]
    groups = [
        ("Localização no índice", steps[:3]),
        ("Recuperação na tabela", steps[3:]),
    ]
    html_parts = []

    for label, group in groups:
        html_parts.extend([f'<div class="flow-label">{label}</div>', '<div class="hash-flow">'])

        for position, (title, value, tone) in enumerate(group):
            html_parts.append(
                f'<div class="flow-step flow-{tone}">'
                f"<small>{escape(title)}</small>"
                f"<strong>{escape(str(value))}</strong></div>"
            )
            if position < len(group) - 1:
                html_parts.append('<div class="flow-arrow">→</div>')

        html_parts.append("</div>")

    st.markdown("".join(html_parts), unsafe_allow_html=True)


def render_bucket_neighborhood(
    bucket_id,
    buckets,
    overflow_buckets,
    fr,
    visible_bucket_count=5,
):
    """Mostra o bucket acessado no contexto de seus vizinhos."""
    bucket_count = len(buckets)
    visible_bucket_count = min(visible_bucket_count, bucket_count)
    half_window = visible_bucket_count // 2
    start = max(0, bucket_id - half_window)
    start = min(start, bucket_count - visible_bucket_count)
    stop = start + visible_bucket_count
    cards = []

    for current_id in range(start, stop):
        primary_count = len(buckets[current_id])
        overflow_count = len(overflow_buckets[current_id])
        accessed_class = " bucket-mini-accessed" if current_id == bucket_id else ""
        marker = "<span>ACESSADO</span>" if current_id == bucket_id else "<span>&nbsp;</span>"
        cards.append(
            f'<div class="bucket-mini{accessed_class}">'
            f"{marker}"
            f"<strong>Bucket {format_number(current_id)}</strong>"
            f"<small>Principal {primary_count}/{fr}</small>"
            f"<small>Overflow {overflow_count}</small>"
            "</div>"
        )

    st.markdown("#### Bucket acessado no contexto")
    st.markdown(
        f'<div class="bucket-neighborhood">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def render_bucket_contents(
    bucket_id,
    buckets,
    overflow_buckets,
    fr,
    highlighted_key=None,
    location=None,
    bucket_position=None,
):
    primary_entries = buckets[bucket_id]
    overflow_entries = overflow_buckets[bucket_id]

    st.markdown(f"#### Bucket {format_number(bucket_id)}")
    st.caption(
        f"Principal: {len(primary_entries)}/{fr} · "
        f"Overflow: {len(overflow_entries)} entradas"
    )
    st.progress(len(primary_entries) / fr)

    if location == "primary":
        st.success(
            f"A chave foi localizada na posição {bucket_position} do bucket principal."
        )
    elif location == "overflow":
        st.warning(
            f"A chave foi localizada na posição {bucket_position} da área de overflow."
        )

    st.markdown("**Bucket principal**")
    show_dataframe(
        make_bucket_dataframe(primary_entries, capacity=fr),
        height=390,
        highlighted_key=highlighted_key,
        key_column="Chave",
    )
    st.markdown("**Área de overflow**")

    if not overflow_entries:
        st.info("Este bucket não possui registros em overflow.")
    else:
        show_dataframe(
            make_bucket_dataframe(overflow_entries),
            height=min(300, 75 + len(overflow_entries) * 35),
            highlighted_key=highlighted_key,
            key_column="Chave",
        )


def render_page_contents(page_id, pages, highlighted_key=None, record_position=None):
    page = pages[page_id]
    st.markdown(f"#### Página {format_number(page_id)}")

    if record_position is None:
        st.caption(f"{format_number(len(page))} registros")
        show_dataframe(make_page_dataframe(page), height=520)
        return

    st.success(
        f"'{highlighted_key}' está na posição {format_number(record_position)} da página."
    )
    start = max(0, record_position - 2)
    stop = min(len(page), record_position + 3)
    st.markdown("**Trecho ao redor do registro encontrado**")
    show_dataframe(
        make_page_dataframe(page, start=start, stop=stop),
        height=245,
        highlighted_key=highlighted_key,
        key_column="Registro",
    )

    with st.expander("Ver todos os registros desta página"):
        show_dataframe(
            make_page_dataframe(page),
            height=520,
            highlighted_key=highlighted_key,
            key_column="Registro",
        )
