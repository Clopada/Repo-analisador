import html as html_lib


def _escapar(s):
    return html_lib.escape(str(s if s is not None else ''))


def _cor_badge(decisao):
    d = decisao.lower()
    if "aprov" in d: return "#dcfce7"
    if "reprov" in d: return "#fee2e2"
    if "pendent" in d: return "#fef3c7"
    return "#e2e8f0"


def gerar_corpo_email(vaga, avaliacoes):
    ordenados = sorted(
        avaliacoes,
        key=lambda c: c.get("avaliacao_vaga", {}).get("score_geral", 0),
        reverse=True
    )

    linhas = ""
    for i, c in enumerate(ordenados, 1):
        ident = c.get("identificacao_candidato", {})
        aval = c.get("avaliacao_vaga", {})
        nome = _escapar(ident.get("nome", "N/A"))
        cargo = _escapar(ident.get("cargo_declarado", "N/A"))
        score = aval.get("score_geral", 0)
        decisao = _escapar(aval.get("decisao_triagem", "Em Análise"))
        cor = _cor_badge(decisao)

        linhas += f"""<tr>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:center;font-weight:bold;">#{i}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;font-weight:600;">{nome}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;">{cargo}</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:center;font-weight:bold;">{score}/100</td>
            <td style="padding:10px;border-bottom:1px solid #e2e8f0;text-align:center;">
                <span style="padding:4px 8px;border-radius:4px;font-size:12px;font-weight:bold;background:{cor};">{decisao}</span>
            </td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f1f5f9;margin:0;padding:20px;color:#0f172a;">
<div style="max-width:800px;background:#fff;margin:0 auto;border-radius:8px;padding:25px;">
  <h1 style="margin-top:0;">📊 Relatório Consolidado de Triagem (Lote)</h1>
  <div style="background:#e0f2fe;border-left:4px solid #0284c7;padding:12px 15px;margin-bottom:20px;border-radius:4px;">
    <p style="margin:0;color:#0369a1;font-weight:bold;">Vaga: {_escapar(vaga.title())}</p>
    <p style="margin:4px 0 0;color:#075985;font-size:14px;">Total: <strong>{len(ordenados)}</strong></p>
  </div>
  <h2 style="color:#1e293b;border-bottom:2px solid #e2e8f0;padding-bottom:8px;">🏆 Ranking de Candidatos</h2>
  <table style="width:100%;border-collapse:collapse;margin-bottom:20px;font-size:14px;">
    <thead><tr style="background:#f1f5f9;text-align:left;color:#475569;">
      <th style="padding:10px;text-align:center;">#</th>
      <th style="padding:10px;">Candidato</th>
      <th style="padding:10px;">Cargo</th>
      <th style="padding:10px;text-align:center;">Score</th>
      <th style="padding:10px;text-align:center;">Decisão</th>
    </tr></thead>
    <tbody>{linhas}</tbody>
  </table>
  <div style="background:#fefce8;border-left:4px solid #ca8a04;padding:12px 15px;border-radius:4px;">
    <p style="margin:0;color:#713f12;font-size:14px;">📎 O <strong>relatório detalhado</strong> está no anexo <strong>relatorio_completo.html</strong>. Os <strong>currículos originais (PDF)</strong> também estão anexados.</p>
  </div>
</div></body></html>"""


def gerar_anexo_relatorio(vaga, avaliacoes, arquivos_originais):
    ordenados = sorted(
        avaliacoes,
        key=lambda c: c.get("avaliacao_vaga", {}).get("score_geral", 0),
        reverse=True
    )

    detalhes = ""
    for i, c in enumerate(ordenados, 1):
        ident = c.get("identificacao_candidato", {})
        aval = c.get("avaliacao_vaga", {})
        contato = ident.get("contato", {}) or {}

        nome = _escapar(ident.get("nome", "N/A"))
        cargo = _escapar(ident.get("cargo_declarado", "N/A"))
        tempo = _escapar(ident.get("tempo_experiencia_estimado", "N/A"))
        email = _escapar(contato.get("email", "N/A"))
        tel = _escapar(contato.get("telefone", "N/A"))
        loc = _escapar(contato.get("localizacao", "N/A"))
        score = aval.get("score_geral", 0)
        decisao = _escapar(aval.get("decisao_triagem", "Em Análise"))
        parecer = _escapar(aval.get("justificativa_coerencia", "Sem justificativa."))
        cor = _cor_badge(decisao)

        idx = c.get("indice_curriculo", i)
        arq = next((a for a in arquivos_originais if a.get("posicao") == idx), None)
        nome_arquivo = _escapar(arq["nome_arquivo"] if arq else f"curriculo_{idx}.pdf")

        detalhes += f"""<div style="margin-bottom:14px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;overflow:hidden;">
    <div style="padding:12px 16px;background:#f8fafc;border-bottom:1px solid #e2e8f0;">
      <span style="font-weight:600;color:#1e293b;">#{i} — {nome}</span>
      <span style="color:#94a3b8;font-size:13px;">({cargo})</span>
      <span style="float:right;">
        <span style="font-weight:bold;font-size:14px;color:#1e293b;margin-right:8px;">{score}/100</span>
        <span style="padding:4px 8px;border-radius:4px;font-size:12px;font-weight:bold;background:{cor};">{decisao}</span>
      </span>
    </div>
    <div style="padding:14px 16px;">
      <p style="margin:0 0 6px;color:#475569;font-size:14px;"><strong>Cargo:</strong> {cargo} | <strong>Exp:</strong> {tempo}</p>
      <p style="margin:0 0 12px;color:#64748b;font-size:13px;"><strong>Contato:</strong> {email} • {tel} • {loc}</p>
      <p style="margin:0 0 10px;color:#334155;font-size:14px;line-height:1.5;"><strong>Parecer:</strong> {parecer}</p>
      <p style="margin:0;color:#0284c7;font-size:13px;font-weight:bold;">📄 Currículo em anexo: {nome_arquivo}</p>
    </div>
  </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f1f5f9;margin:0;padding:20px;color:#0f172a;">
<div style="max-width:800px;background:#fff;margin:0 auto;border-radius:8px;padding:25px;">
  <h1 style="margin-top:0;">📊 Relatório Completo — {_escapar(vaga.title())}</h1>
  <p style="color:#475569;">Total: <strong>{len(ordenados)}</strong></p>
  {detalhes}
</div></body></html>"""