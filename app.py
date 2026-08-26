import os
import re
import traceback
import uuid
from datetime import datetime
from urllib.parse import quote
import requests
from flask import Flask, redirect, render_template_string, request, session, url_for
from gsheet_utils import append_to_sheet

ALLOWED_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9_.+-]+@((gmail|hotmail|outlook|yahoo)\.(com|com\.br))$",
    re.IGNORECASE,
)
NAME_PATTERN = re.compile(r"[A-Za-z\u00C0-\u00FF '\u00b4`^~.-]+")
VALID_DDDS = {
    "11", "12", "13", "14", "15", "16", "17", "18", "19",
    "21", "22", "24", "27", "28",
    "31", "32", "33", "34", "35", "37", "38",
    "41", "42", "43", "44", "45", "46", "47", "48", "49",
    "51", "53", "54", "55",
    "61", "62", "63", "64", "65", "66", "67", "68", "69",
    "71", "73", "74", "75", "77", "79",
    "81", "82", "83", "84", "85", "86", "87", "88", "89",
    "91", "92", "93", "94", "95", "96", "97", "98", "99",
}
CURSOS_DISPONIVEIS = [
    {"id": "01", "nome": "TRANCISTA"},
]
COURSE_OPTIONS = [
    {
        "id": "1",
        "curso_id": "01",
        "curso": "TRANCISTA",
        "turma": "TURMA 1.1",
        "local": "INSTITUTO SOCIAL F\u00caINIX",
        "dias_aula": "Ter\u00e7a, Quarta e Quinta",
        "horario": "9h \u00e0s 16h",
        "data_inicio": "01/09/2026",
        "encerramento": "03/09/2026",
        "endereco_curso": "\U0001f4cdRua Florian\u00f3polis, 435 - Pra\u00e7a Seca - CEP 21.321-050",
    },
]
COURSE_OPTIONS_BY_ID = {option["id"]: option for option in COURSE_OPTIONS}
COURSE_INFO = COURSE_OPTIONS[0]
WHATSAPP_SHARE_HOME_URL = "https://mulheres-do-corre-6.onrender.com"

def build_whatsapp_share_url():
    message = (
        "Acabei de me inscrever no programa Mulheres do Corre 5, com cursos gratuitos de "
        "qualificacao profissional da Prefeitura do Rio de Janeiro. Confira aqui: "
        f"{WHATSAPP_SHARE_HOME_URL}"
    )
    return f"https://wa.me/?text={quote(message)}"

def get_course_option(option_id):
    return COURSE_OPTIONS_BY_ID.get(str(option_id or ""))

def fill_form_data_from_option(form_data, option):
    form_data["local"]          = option["local"]
    form_data["curso"]          = option["curso"]
    form_data["turma"]          = option["turma"]
    form_data["dias_aula"]      = option["dias_aula"]
    form_data["horario"]        = option["horario"]
    form_data["data_inicio"]    = option["data_inicio"]
    form_data["encerramento"]   = option["encerramento"]
    form_data["endereco_curso"] = option["endereco_curso"]
TEMPLATE_WIZARD = r"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Mulheres do Corre 5</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="stylesheet" href="/static/assistant.css">
    <link href="https://fonts.googleapis.com/css2?family=Wise:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        :root { --cor-principal:#912922; --cor-principal-escura:#6e1c17; --cor-clara:#fcecea; --cor-texto:#3d1210; --cor-borda:#e8a09c; --sombra-card:0 18px 55px rgba(145,41,34,0.18); }
        * { box-sizing:border-box; } html,body { min-height:100%; margin:0; padding:0; }
        body { min-height:100vh; background:radial-gradient(circle at top left,rgba(145,41,34,0.14),transparent 34%),radial-gradient(circle at top right,rgba(236,180,177,0.82),transparent 32%),linear-gradient(135deg,#fff5f4 0%,#fff 42%,#fce0de 100%); color:var(--cor-texto); font-family:'Wise',Arial,sans-serif; }
        .main-header { border-bottom:4px solid var(--cor-principal); background:rgba(255,255,255,0.92); backdrop-filter:blur(8px); }
        .header-logos { display:flex; flex-direction:column; align-items:center; gap:10px; padding:10px 12px; }
        .header-logos img { max-width:min(88vw,280px); height:auto; }
        .wizard-page { width:min(900px,98vw); margin:0 auto; padding:8px 0 18px; text-align:center; }
        .wizard-progress { margin:18px auto 22px; padding:18px; border-radius:28px; background:rgba(255,255,255,0.9); box-shadow:0 12px 30px rgba(145,41,34,0.12); }
        .wizard-track { width:100%; height:14px; background:#fce0de; border-radius:999px; overflow:hidden; }
        .wizard-fill { height:100%; width:25%; background:linear-gradient(90deg,#912922 0%,#d4645b 100%); border-radius:999px; transition:width 0.3s ease; }
        .wizard-labels { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:14px; }
        .wizard-label { padding:12px 10px; border:1px solid #e8a09c; border-radius:18px; background:#fff; color:#7a2520; font-size:0.92rem; font-weight:700; text-align:center; transition:all 0.25s ease; }
        .wizard-label.ativo { border-color:var(--cor-principal); background:var(--cor-clara); color:var(--cor-principal); }
        .wizard-shell { background:rgba(255,255,255,0.88); border:1px solid rgba(255,255,255,0.9); border-radius:34px; box-shadow:var(--sombra-card); overflow:hidden; }
        .wizard-panel { display:none; padding:18px 8px; animation:surgir 0.28s ease; }
        .wizard-panel.ativo { display:block; }
        @keyframes surgir { from{opacity:0;transform:translateY(12px);} to{opacity:1;transform:translateY(0);} }
        .hero-grid { display:grid; grid-template-columns:minmax(0,1fr); gap:14px; align-items:center; justify-items:center; }
        .hero-card { padding:32px; border-radius:30px; background:linear-gradient(135deg,#fff 0%,#fff5f4 58%,#fce0de 100%); border:1px solid #e8a09c; width:100%; text-align:center; }
        .hero-pill { display:inline-flex; align-items:center; gap:8px; padding:10px 18px; border-radius:999px; background:var(--cor-principal); color:#fff; font-size:0.95rem; font-weight:800; letter-spacing:0.05em; text-transform:uppercase; }
        .hero-title,.panel-title { margin:18px 0 10px; color:var(--cor-principal); font-size:clamp(2rem,3.8vw,3.2rem); line-height:1; letter-spacing:-0.04em; }
        .panel-title { font-size:clamp(1.7rem,3vw,2.4rem); }
        .hero-subtitle,.panel-subtitle { margin:0; color:#7a2520; font-size:1.05rem; line-height:1.55; }
        .hero-highlights { display:grid; gap:10px; margin-top:16px; }
        .hero-highlight,.info-card,.review-box,.step-card { border-radius:22px; border:1px solid #f0c0bc; background:#fff; box-shadow:0 8px 24px rgba(145,41,34,0.08); }
        .hero-highlight { padding:12px 14px; color:#7a2520; font-size:0.95rem; font-weight:700; }
        .hero-highlight strong { display:block; color:var(--cor-principal); font-size:1.15rem; margin-bottom:4px; }
        .beneficios-rotativo { margin-top:10px; }
        .beneficio-item { display:inline-block; padding:8px 16px; border-radius:999px; background:var(--cor-clara); color:var(--cor-principal); font-size:0.95rem; font-weight:800; }
        .step-card { padding:18px 16px; width:100%; margin:0 auto; text-align:center; }
        .step-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px 12px; margin-top:10px; align-items:start; }
        .step-grid.step-grid--stacked { grid-template-columns:minmax(0,1fr); max-width:540px; margin-left:auto; margin-right:auto; }
        .wizard-panel[data-step="dados"] .form-group,.wizard-panel[data-step="escolher"] .form-group { align-items:stretch; text-align:left; }
        .wizard-panel[data-step="dados"] .form-group label,.wizard-panel[data-step="escolher"] .form-group label { width:100%; text-align:left; }
        .wizard-panel[data-step="escolher"] .step-grid.step-grid--stacked { max-width:470px; }
        .wizard-panel[data-step="escolher"] .form-group,.wizard-panel[data-step="escolher"] .form-group.full { width:100%; max-width:100%; }
        .wizard-panel[data-step="escolher"] .input-with-action { width:100%; max-width:100%; }
        .form-group { display:flex; flex-direction:column; gap:4px; width:100%; align-self:start; align-items:center; text-align:center; }
        .form-group.full { grid-column:1/-1; }
        .form-group label,.review-title,.mini-title { color:var(--cor-principal); font-size:1rem; font-weight:800; }
        .form-group input,.form-group select,.form-group textarea { display:block; width:100%!important; max-width:100%!important; min-width:0!important; margin:0!important; box-sizing:border-box; min-height:38px; height:38px; padding:7px 10px; border:1.2px solid var(--cor-borda); border-radius:10px; background:#fff5f4; color:var(--cor-texto); font:inherit; line-height:1.2; text-align:left; outline:none; transition:border-color 0.2s ease,box-shadow 0.2s ease,background 0.2s ease; }
        .form-group select { appearance:none; -webkit-appearance:none; -moz-appearance:none; background-image:url('data:image/svg+xml;utf8,<svg fill="%23912922" height="20" viewBox="0 0 24 24" width="20" xmlns="http://www.w3.org/2000/svg"><path d="M7 10l5 5 5-5z"/></svg>'); background-repeat:no-repeat; background-position:right 14px center; background-size:20px 20px; padding-right:44px; }
        .form-group textarea { min-height:60px; height:auto; resize:vertical; }
        .form-group input:focus,.form-group select:focus,.form-group textarea:focus { border-color:var(--cor-principal); background:#fff; box-shadow:0 0 0 4px rgba(145,41,34,0.12); }
        .readonly-field { background:#fcecea!important; color:#7a2520!important; font-weight:700; }
        .input-with-action { display:grid; grid-template-columns:minmax(0,1fr); gap:10px; align-items:stretch; }
        .input-with-action input { width:100%!important; }
        .icon-button,.cta-button,.secondary-button,.submit-button { border:none; border-radius:18px; font:inherit; font-weight:800; cursor:pointer; transition:transform 0.16s ease,box-shadow 0.16s ease,background 0.16s ease,color 0.16s ease; }
        .icon-button { min-width:56px; min-height:52px; background:var(--cor-principal); color:#fff; box-shadow:0 8px 16px rgba(145,41,34,0.22); }
        .wizard-panel[data-step="escolher"] .icon-button { width:100%!important; min-width:0!important; max-width:100%!important; height:38px!important; min-height:38px!important; padding:0; border-radius:10px; box-shadow:none; }
        .panel-actions .cta-button,.panel-actions .secondary-button,.panel-actions .submit-button { width:100%!important; max-width:100%!important; min-width:0!important; margin:0!important; height:38px; font-size:1rem; }
        .cta-button,.submit-button { background:linear-gradient(90deg,#912922 0%,#d4645b 100%); color:#fff; box-shadow:0 10px 24px rgba(145,41,34,0.24); }
        .secondary-button { background:#fff; color:var(--cor-principal); border:2px solid var(--cor-principal); }
        .cta-button,.secondary-button,.submit-button { min-height:54px; padding:14px 22px; text-transform:uppercase; letter-spacing:0.04em; }
        .cta-button:hover,.secondary-button:hover,.submit-button:hover,.icon-button:hover { transform:translateY(-1px); }
        .panel-actions { display:flex; flex-direction:column-reverse; align-items:center; gap:12px; justify-content:space-between; margin-top:28px; max-width:420px; margin-left:auto; margin-right:auto; }
        .panel-actions > * { flex:1; }
        .balao-erro { margin-top:4px; padding:10px 14px; border-radius:14px; border:1px solid #6e1c17; background:#912922; color:#fff; font-size:0.92rem; font-weight:700; line-height:1.35; }
        .balao-erro[hidden] { display:none; }
        .erro-campo { border-color:#912922!important; box-shadow:0 0 0 4px rgba(145,41,34,0.12)!important; }
        .review-layout { display:grid; grid-template-columns:1fr; gap:8px; margin-top:10px; max-width:540px; margin-left:auto; margin-right:auto; }
        .review-box { padding:10px; text-align:center; }
        .review-box.full { grid-column:1/-1; }
        .review-list { display:grid; gap:6px; margin-top:8px; text-align:left; }
        .review-item { display:grid; grid-template-columns:auto 1fr; align-items:center; column-gap:8px; padding:7px 9px; border-radius:10px; background:var(--cor-clara); text-align:left; }
        .review-item strong { color:var(--cor-principal); font-size:0.88rem; white-space:nowrap; }
        .review-item strong::after { content:':'; }
        .review-item span { color:var(--cor-texto); font-size:0.94rem; word-break:break-word; text-align:left; }
        .review-check { display:flex; gap:12px; align-items:flex-start; justify-content:flex-start; padding:10px 12px; border-radius:14px; background:var(--cor-clara); color:#3d1210; line-height:1.45; text-align:left; }
        .review-check input { margin-top:3px; width:20px; min-width:20px; height:20px; flex:0 0 20px; accent-color:var(--cor-principal); }
        .review-check span { flex:1 1 auto; min-width:0; }
        .review-check ul { margin:8px 0 0 18px; padding:0; list-style-position:outside; text-align:left; }
        .review-box .form-group { align-items:stretch; text-align:left; }
        .review-box .form-group label { width:100%; text-align:left; }
        @media(max-width:860px){.hero-grid,.review-layout{grid-template-columns:1fr;}.step-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;}.step-grid.step-grid--stacked{grid-template-columns:minmax(0,1fr);max-width:540px;}}
        @media(max-width:640px){
            html,body{width:100%!important;max-width:100%!important;overflow-x:hidden!important;}body*{min-width:0;}body{overflow-x:hidden;}
            .wizard-page{width:calc(100% - 8px)!important;max-width:100%!important;padding:4px 0 10px;}.wizard-progress,.wizard-panel{width:100%!important;max-width:100%!important;padding:8px;}.wizard-labels{grid-template-columns:1fr;gap:6px;}
            .hero-card,.step-card,.review-box{width:100%!important;max-width:100%!important;padding:8px;}.input-with-action{grid-template-columns:minmax(0,1fr);width:100%!important;max-width:100%!important;}.panel-actions>*{width:100%;}
            .step-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;}.step-grid.step-grid--stacked{grid-template-columns:minmax(0,1fr);max-width:100%;}.review-layout{grid-template-columns:1fr;max-width:100%;gap:10px;}
            .review-item,.form-group,.form-group input,.form-group select,.form-group textarea,.wizard-shell,.panel-actions,.review-check,.balao-erro{width:100%!important;max-width:100%!important;}
            .form-group label,.review-title,.review-item span,.review-check{word-break:break-word;}img,svg{max-width:100%!important;height:auto!important;}
            .form-group input,.form-group select,.form-group textarea,.icon-button{min-height:32px;height:32px;font-size:0.98em;}.form-group textarea{min-height:60px;height:auto;}
            .review-check{flex-direction:row;align-items:flex-start;padding:8px;}.review-check input{width:22px;min-width:22px;height:22px;flex-basis:22px;}.review-check ul{padding-left:2px;}
            .hero-title,.panel-title{font-size:1.3rem;}.hero-subtitle,.panel-subtitle{font-size:0.92rem;}.wizard-shell{border-radius:16px;}.form-group.full{grid-column:auto;}
        }
    </style>
</head>
<body data-start-step="{{ current_step }}">
    <script src="/static/assistant.js"></script>
    <header class="main-header">
        <div class="header-logos">
            <img src="/static/logo-prefeitura.png" alt="Prefeitura do Rio" class="logo-prefeitura-topo">
        </div>
    </header>
    <div class="wizard-page">
        <div class="wizard-progress">
            <div class="wizard-track"><div class="wizard-fill" id="wizard-fill"></div></div>
            <div class="wizard-labels">
                <div class="wizard-label" data-step-label="index">1. Inicio</div>
                <div class="wizard-label" data-step-label="dados">2. Dados pessoais</div>
                <div class="wizard-label" data-step-label="escolher">3. Escolher</div>
                <div class="wizard-label" data-step-label="revisao">4. Revisao</div>
            </div>
        </div>
        <div class="wizard-shell">
            <form id="wizard-form" method="POST" action="{{ url_for('inscricao_unica') }}" autocomplete="off" novalidate>
                <section class="wizard-panel" data-step="index">
                    <div class="hero-grid"><div class="hero-card">
                        <span class="hero-pill">PROGRAMA: MULHERES DO CORRE</span>
                        <h1 class="hero-title">MULHERES DO CORRE 5</h1>
                        <p class="hero-subtitle">Mulheres que constroem o pr&#243;prio futuro.</p>
                        <div class="hero-highlights">
                            <div class="hero-highlight">
                                <strong>CURSOS DISPON&#205;VEIS</strong><br>
                                &#9986;&#65039; TRANCISTA
                            </div>
                            <div class="hero-highlight">
                                <strong>BENEF&#205;CIOS</strong>
                                <div class="beneficios-rotativo">
                                    <span class="beneficio-item active-beneficio">100% gratuito</span>
                                    <span class="beneficio-item" style="display:none;">Material did&#225;tico incluso</span>
                                    <span class="beneficio-item" style="display:none;">Certificado de conclus&#227;o</span>
                                </div>
                            </div>
                        </div>
                        <div class="panel-actions">
                            <button type="button" class="cta-button" data-next="dados">Come&#231;ar inscri&#231;&#227;o</button>
                        </div>
                    </div></div>
                </section>
                <section class="wizard-panel" data-step="dados">
                    <div class="step-card">
                        <h2 class="panel-title">Dados pessoais</h2>
                        <div class="step-grid step-grid--stacked">
                            <div class="form-group full"><label for="nome">Nome completo *</label><input type="text" id="nome" name="nome" maxlength="50" placeholder="Digite seu nome completo" value="{{ form_data.get('nome', '') }}"><div class="balao-erro" id="nome-error" {% if not errors.get('nome') %}hidden{% endif %}>{{ errors.get('nome', '') }}</div></div>
                            <div class="form-group"><label for="genero">G&#234;nero *</label><select id="genero" name="genero"><option value="">Selecione</option>{% for genero in generos %}<option value="{{ genero }}" {% if form_data.get('genero') == genero %}selected{% endif %}>{{ genero }}</option>{% endfor %}</select><div class="balao-erro" id="genero-error" {% if not errors.get('genero') %}hidden{% endif %}>{{ errors.get('genero', '') }}</div></div>
                            <div class="form-group"><label for="cpf">CPF *</label><input type="text" id="cpf" name="cpf" maxlength="14" placeholder="000.000.000-00" value="{{ form_data.get('cpf', '') }}"><div class="balao-erro" id="cpf-error" {% if not errors.get('cpf') %}hidden{% endif %}>{{ errors.get('cpf', '') }}</div></div>
                            <div class="form-group"><label for="nascimento">Data de nascimento *</label><input type="text" id="nascimento" name="nascimento" maxlength="10" placeholder="dd/mm/aaaa" value="{{ form_data.get('nascimento', '') }}"><div class="balao-erro" id="nascimento-error" {% if not errors.get('nascimento') %}hidden{% endif %}>{{ errors.get('nascimento', '') }}</div></div>
                            <div class="form-group"><label for="whatsapp">WhatsApp *</label><input type="text" id="whatsapp" name="whatsapp" maxlength="16" placeholder="(00) 00000-0000" value="{{ form_data.get('whatsapp', '') }}"><div class="balao-erro" id="whatsapp-error" {% if not errors.get('whatsapp') %}hidden{% endif %}>{{ errors.get('whatsapp', '') }}</div></div>
                            <div class="form-group"><label for="cep">CEP *</label><input type="text" id="cep" name="cep" maxlength="9" placeholder="00000-000" value="{{ form_data.get('cep', '') }}"><div class="balao-erro" id="cep-error" {% if not errors.get('cep') %}hidden{% endif %}>{{ errors.get('cep', '') }}</div></div>
                            <div class="form-group"><label for="bairro">Bairro *</label><input type="text" id="bairro" name="bairro" maxlength="40" placeholder="Nome do bairro" value="{{ form_data.get('bairro', '') }}"><div class="balao-erro" id="bairro-error" {% if not errors.get('bairro') %}hidden{% endif %}>{{ errors.get('bairro', '') }}</div></div>
                            <div class="form-group full"><label for="email">E-mail *</label><input type="email" id="email" name="email" maxlength="60" placeholder="seuemail@gmail.com" value="{{ form_data.get('email', '') }}"><div class="balao-erro" id="email-error" {% if not errors.get('email') %}hidden{% endif %}>{{ errors.get('email', '') }}</div></div>
                        </div>
                        <div class="panel-actions">
                            <button type="button" class="secondary-button" data-prev="index">Voltar</button>
                            <button type="button" class="cta-button" data-next="escolher">Pr&#243;ximo</button>
                        </div>
                    </div>
                </section>
                <section class="wizard-panel" data-step="escolher">
                    <div class="step-card">
                        <h2 class="panel-title">Informa&#231;&#245;es do curso</h2>
                        <div class="step-grid step-grid--stacked">
                            <div class="form-group full"><label for="curso_select">Selecione o curso *</label><select id="curso_select" name="curso_select"><option value="" selected>Selecione um curso</option>{% for curso in cursos_disponiveis %}<option value="{{ curso.id }}">{{ curso.nome }}</option>{% endfor %}</select></div>
                            <div class="form-group full" id="local-select-group"><label for="local_select">Selecione o local *</label><select id="local_select"><option value="">Selecione um local</option></select></div>
                            <div class="form-group full" id="turma-select-group" style="display:none;"><label for="turma_select">Selecione a turma *</label><select id="turma_select"><option value="">Selecione uma turma</option></select><div class="balao-erro" id="opcao_id-error" {% if not errors.get('opcao_id') %}hidden{% endif %}>{{ errors.get('opcao_id', '') }}</div></div>
                            <input type="hidden" id="hidden_opcao_id" name="opcao_id" value="{{ form_data.get('opcao_id', '') }}">
                            <div class="form-group full" id="info-curso-group" style="display:none;"><label for="curso">Curso</label><input type="text" id="curso" name="curso" class="readonly-field" readonly value="{{ form_data.get('curso', '') }}"></div>
                            <div class="form-group full" id="info-turma-group" style="display:none;"><label for="turma">Turma</label><input type="text" id="turma" name="turma" class="readonly-field" readonly value="{{ form_data.get('turma', '') }}"></div>
                            <div class="form-group full" id="info-local-group" style="display:none;"><label for="local_nome">Local</label><input type="text" id="local_nome" class="readonly-field" readonly value="{{ form_data.get('local', '') }}"></div>
                            <div class="form-group" id="info-dias-group" style="display:none;"><label for="dias_aula">Dias de aula</label><input type="text" id="dias_aula" name="dias_aula" class="readonly-field" readonly value="{{ form_data.get('dias_aula', '') }}"></div>
                            <div class="form-group" id="info-horario-group" style="display:none;"><label for="horario">Hor&#225;rio</label><input type="text" id="horario" name="horario" class="readonly-field" readonly value="{{ form_data.get('horario', '') }}"></div>
                            <div class="form-group" id="info-inicio-group" style="display:none;"><label for="data_inicio">Data de in&#237;cio</label><input type="text" id="data_inicio" name="data_inicio" class="readonly-field" readonly value="{{ form_data.get('data_inicio', '') }}"></div>
                            <div class="form-group" id="info-enc-group" style="display:none;"><label for="encerramento">Data de encerramento</label><input type="text" id="encerramento" name="encerramento" class="readonly-field" readonly value="{{ form_data.get('encerramento', '') }}"></div>
                            <div class="form-group full" id="info-endereco-group" style="display:none;"><label for="endereco_curso">Endere&#231;o da unidade</label><div class="input-with-action"><input type="text" id="endereco_curso" name="endereco_curso" class="readonly-field" readonly value="{{ form_data.get('endereco_curso', '') }}"><button type="button" class="icon-button" id="btn-copiar-endereco" title="Copiar endere&#231;o">Copiar &#128203;</button></div></div>
                        </div>
                        <div class="panel-actions">
                            <button type="button" class="secondary-button" data-prev="dados">Voltar</button>
                            <button type="button" class="cta-button" data-next="revisao">Ir para revis&#227;o</button>
                        </div>
                    </div>
                </section>
                <section class="wizard-panel" data-step="revisao">
                    <div class="step-card">
                        <h2 class="panel-title">Revise antes de finalizar</h2>
                        <p class="panel-subtitle">Confira os dados preenchidos e confirme sua participa&#231;&#227;o.</p>
                        <div class="review-layout">
                            <div class="review-box"><div class="review-title">Dados pessoais</div><div class="review-list">
                                <div class="review-item"><strong>Nome</strong><span data-review="nome"></span></div>
                                <div class="review-item"><strong>CPF</strong><span data-review="cpf"></span></div>
                                <div class="review-item"><strong>Nascimento</strong><span data-review="nascimento"></span></div>
                                <div class="review-item"><strong>G&#234;nero</strong><span data-review="genero"></span></div>
                                <div class="review-item"><strong>WhatsApp</strong><span data-review="whatsapp"></span></div>
                                <div class="review-item"><strong>CEP</strong><span data-review="cep"></span></div>
                                <div class="review-item"><strong>Bairro</strong><span data-review="bairro"></span></div>
                                <div class="review-item"><strong>E-mail</strong><span data-review="email"></span></div>
                            </div></div>
                            <div class="review-box"><div class="review-title">Informa&#231;&#245;es do curso</div><div class="review-list">
                                <div class="review-item"><strong>Curso</strong><span data-review="curso"></span></div>
                                <div class="review-item"><strong>Turma</strong><span data-review="turma"></span></div>
                                <div class="review-item"><strong>Local</strong><span data-review="local_nome"></span></div>
                                <div class="review-item"><strong>Dias de aula</strong><span data-review="dias_aula"></span></div>
                                <div class="review-item"><strong>Hor&#225;rio</strong><span data-review="horario"></span></div>
                                <div class="review-item"><strong>In&#237;cio previsto</strong><span data-review="data_inicio"></span></div>
                                <div class="review-item"><strong>Encerramento</strong><span data-review="encerramento"></span></div>
                                <div class="review-item"><strong>Endere&#231;o</strong><span data-review="endereco_curso"></span></div>
                            </div></div>
                            <div class="review-box full"><div class="form-group"><label for="como_conheceu">Como conheceu (opcional)</label><input type="text" id="como_conheceu" name="como_conheceu" maxlength="120" placeholder="Digite como conheceu o projeto" value="{{ form_data.get('como_conheceu', '') }}"><div class="balao-erro" id="como_conheceu-error" {% if not errors.get('como_conheceu') %}hidden{% endif %}>{{ errors.get('como_conheceu', '') }}</div></div></div>
                            <div class="review-box full">
                                <div style="margin-bottom:10px;color:#7a2520;font-size:0.98rem;text-align:left;"><strong>Elegibilidade:</strong> Esta inscri&#231;&#227;o &#233; destinada a pessoas interessadas nos cursos de qualifica&#231;&#227;o profissional do programa Mulheres do Corre 5.</div>
                                <label class="review-check" for="confirma_dados">
                                    <input type="checkbox" id="confirma_dados" name="confirma_dados" value="sim" {% if form_data.get('confirma_dados') %}checked{% endif %}>
                                    <span>Confirmo que tenho interesse em participar do programa Mulheres do Corre 5 e em uma das turmas de qualifica&#231;&#227;o dispon&#237;veis.<br>Todas as informa&#231;&#245;es fornecidas s&#227;o verdadeiras e estou de acordo com os termos de participa&#231;&#227;o.<br>Autorizo o uso dos meus dados para fins de inscri&#231;&#227;o e contato relacionado ao curso.<br>Tamb&#233;m autorizo o uso da minha imagem para divulga&#231;&#227;o nos canais de comunica&#231;&#227;o e redes sociais do projeto e da Prefeitura do Rio.</span>
                                </label>
                                <div style="margin-top:10px;"><strong>Ao confirmar voc&#234; declara a ci&#234;ncia de que:</strong><ul><li>O curso &#233; totalmente gratuito</li><li>As vagas s&#227;o limitadas e dependem de confirma&#231;&#227;o</li><li>Os dados ser&#227;o usados apenas para inscri&#231;&#227;o e contato</li></ul></div>
                                <div class="balao-erro" id="confirma_dados-error" {% if not errors.get('confirma_dados') %}hidden{% endif %}>{{ errors.get('confirma_dados', '') }}</div>
                            </div>
                        </div>
                        <div class="panel-actions">
                            <button type="button" class="secondary-button" data-prev="escolher">Voltar</button>
                            <button type="submit" class="submit-button">Finalizar inscri&#231;&#227;o</button>
                        </div>
                    </div>
                </section>
            </form>
        </div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function () {
            var stepOrder=['index','dados','escolher','revisao'];
            var progressByStep={index:25,dados:45,escolher:70,revisao:90};
            var form=document.getElementById('wizard-form'),fill=document.getElementById('wizard-fill');
            var startStep=document.body.dataset.startStep||'index';
            var panels=Array.from(document.querySelectorAll('[data-step]'));
            var labels=Array.from(document.querySelectorAll('[data-step-label]'));
            var reviewTargets=Array.from(document.querySelectorAll('[data-review]'));
            var courseOptions={{ course_options|tojson }};
            var courseOptionsById=Object.fromEntries(courseOptions.map(function(o){return[String(o.id),o];}));
            var optionsByCursoId={};
            courseOptions.forEach(function(o){if(!optionsByCursoId[o.curso_id])optionsByCursoId[o.curso_id]=[];optionsByCursoId[o.curso_id].push(o);});
            var nomeInput=document.getElementById('nome'),generoInput=document.getElementById('genero'),cpfInput=document.getElementById('cpf'),nascimentoInput=document.getElementById('nascimento'),whatsappInput=document.getElementById('whatsapp'),cepInput=document.getElementById('cep'),bairroInput=document.getElementById('bairro'),emailInput=document.getElementById('email');
            var cursoSelect=document.getElementById('curso_select'),localSelectEl=document.getElementById('local_select'),turmaSelect=document.getElementById('turma_select'),localSelectGroup=document.getElementById('local-select-group'),turmaSelectGroup=document.getElementById('turma-select-group');
            var cursoInput=document.getElementById('curso'),turmaInput=document.getElementById('turma'),localInput=document.getElementById('local_nome'),diasAulaInput=document.getElementById('dias_aula'),horarioInput=document.getElementById('horario'),dataInicioInput=document.getElementById('data_inicio'),encerramentoInput=document.getElementById('encerramento'),enderecoInput=document.getElementById('endereco_curso'),confirmaDadosInput=document.getElementById('confirma_dados'),btnCopiarEndereco=document.getElementById('btn-copiar-endereco');
            var infoCursoGroup=document.getElementById('info-curso-group'),infoCursoGroup2=document.getElementById('info-turma-group'),infoLocalGroup=document.getElementById('info-local-group'),infoDiasGroup=document.getElementById('info-dias-group'),infoHorarioGroup=document.getElementById('info-horario-group'),infoInicioGroup=document.getElementById('info-inicio-group'),infoEncGroup=document.getElementById('info-enc-group'),infoEndGroup=document.getElementById('info-endereco-group');
            var allInfoGroups=[infoCursoGroup,infoCursoGroup2,infoLocalGroup,infoDiasGroup,infoHorarioGroup,infoInicioGroup,infoEncGroup,infoEndGroup];
            function somenteDigitos(v){return(v||'').replace(/\D/g,'');}
            function setError(id,msg){var f=document.getElementById(id),e=document.getElementById(id+'-error');if(f)f.classList.toggle('erro-campo',Boolean(msg));if(e){e.textContent=msg||'';e.hidden=!msg;}}
            function mostrarInfoCurso(show){allInfoGroups.forEach(function(el){if(el)el.style.display=show?'':'none';});}
            function aplicarOpcaoCurso(optionId){var option=courseOptionsById[String(optionId||'')];if(!option){var h=document.getElementById('hidden_opcao_id');if(h)h.value='';cursoInput.value='';turmaInput.value='';localInput.value='';diasAulaInput.value='';horarioInput.value='';dataInicioInput.value='';encerramentoInput.value='';enderecoInput.value='';mostrarInfoCurso(false);return;}var h=document.getElementById('hidden_opcao_id');if(h)h.value=optionId;cursoInput.value=option.curso;turmaInput.value=option.turma;localInput.value=option.local;diasAulaInput.value=option.dias_aula;horarioInput.value=option.horario;dataInicioInput.value=option.data_inicio;encerramentoInput.value=option.encerramento;enderecoInput.value=option.endereco_curso;mostrarInfoCurso(true);setError('opcao_id','');syncReview();}
            function atualizarLocais(){var cursoId=cursoSelect.value;localSelectEl.innerHTML='';turmaSelect.innerHTML='';localSelectGroup.style.display='none';turmaSelectGroup.style.display='none';aplicarOpcaoCurso('');if(!cursoId)return;var turmasDoCurso=(optionsByCursoId[cursoId]||[]);var locaisVistos=[],locaisUnicos=[];turmasDoCurso.forEach(function(t){if(locaisVistos.indexOf(t.local)===-1){locaisVistos.push(t.local);locaisUnicos.push(t.local);}});if(locaisUnicos.length===0)return;localSelectGroup.style.display='';var ph=document.createElement('option');ph.value='';ph.textContent='Selecione um local';localSelectEl.appendChild(ph);locaisUnicos.forEach(function(local){var opt=document.createElement('option');opt.value=local;opt.textContent=local;localSelectEl.appendChild(opt);});}
            function atualizarTurmas(){var cursoId=cursoSelect.value,localVal=localSelectEl.value;turmaSelect.innerHTML='';turmaSelectGroup.style.display='none';aplicarOpcaoCurso('');if(!cursoId||!localVal)return;var turmasFiltradas=(optionsByCursoId[cursoId]||[]).filter(function(t){return t.local===localVal;});if(turmasFiltradas.length===0)return;if(turmasFiltradas.length===1){turmaSelectGroup.style.display='none';aplicarOpcaoCurso(turmasFiltradas[0].id);return;}turmaSelectGroup.style.display='';var ph=document.createElement('option');ph.value='';ph.textContent='Selecione uma turma';turmaSelect.appendChild(ph);turmasFiltradas.forEach(function(t){var opt=document.createElement('option');opt.value=t.id;opt.textContent=t.turma;turmaSelect.appendChild(opt);});}
            function mostrarPasso(step){panels.forEach(function(p){p.classList.toggle('ativo',p.dataset.step===step);});labels.forEach(function(l){l.classList.toggle('ativo',l.dataset.stepLabel===step);});fill.style.width=(progressByStep[step]||25)+'%';window.scrollTo({top:0,behavior:'smooth'});}
            function syncReview(){reviewTargets.forEach(function(t){var f=document.getElementById(t.dataset.review);if(!f){t.textContent='';return;}if(f.tagName==='SELECT'){var s=f.options[f.selectedIndex];t.textContent=s?s.text.trim():'';}else{t.textContent=f.value.trim();}});}
            function validarCPF(cpf){var d=somenteDigitos(cpf);if(d.length!==11||/^(\d)\1+$/.test(d))return false;var s=0,g;for(var i=0;i<9;i++)s+=Number(d[i])*(10-i);g=(s*10)%11;if(g===10)g=0;if(g!==Number(d[9]))return false;s=0;for(var i=0;i<10;i++)s+=Number(d[i])*(11-i);g=(s*10)%11;if(g===10)g=0;return g===Number(d[10]);}
            function validarEmail(e){return/^[a-zA-Z0-9_.+-]+@((gmail|hotmail|outlook|yahoo)\.(com|com\.br))$/i.test((e||'').trim());}
            function idadePermitida(v){var p=(v||'').split('/');if(p.length!==3)return false;var dia=Number(p[0]),mes=Number(p[1])-1,ano=Number(p[2]);var d=new Date(ano,mes,dia);if(isNaN(d.getTime())||d.getDate()!==dia||d.getMonth()!==mes||d.getFullYear()!==ano)return false;var hoje=new Date();var idade=hoje.getFullYear()-d.getFullYear();if(hoje.getMonth()-d.getMonth()<0||(hoje.getMonth()===d.getMonth()&&hoje.getDate()<d.getDate()))idade--;return idade>=16&&idade<=90;}
            function validarDDD(w){var d=somenteDigitos(w);if(d.length<11)return false;return['11','12','13','14','15','16','17','18','19','21','22','24','27','28','31','32','33','34','35','37','38','41','42','43','44','45','46','47','48','49','51','53','54','55','61','62','63','64','65','66','67','68','69','71','73','74','75','77','79','81','82','83','84','85','86','87','88','89','91','92','93','94','95','96','97','98','99'].includes(d.slice(0,2));}
            function mascCPF(){var v=somenteDigitos(cpfInput.value).slice(0,11);if(v.length>9)v=v.replace(/(\d{3})(\d{3})(\d{3})(\d{1,2})/,'$1.$2.$3-$4');else if(v.length>6)v=v.replace(/(\d{3})(\d{3})(\d{1,3})/,'$1.$2.$3');else if(v.length>3)v=v.replace(/(\d{3})(\d{1,3})/,'$1.$2');cpfInput.value=v;}
            function mascNasc(){var v=somenteDigitos(nascimentoInput.value).slice(0,8);if(v.length>4)v=v.replace(/(\d{2})(\d{2})(\d{1,4})/,'$1/$2/$3');else if(v.length>2)v=v.replace(/(\d{2})(\d{1,2})/,'$1/$2');nascimentoInput.value=v;}
            function mascWpp(){var v=somenteDigitos(whatsappInput.value).slice(0,11);if(v.length>6)v=v.replace(/(\d{2})(\d{5})(\d{0,4})/,'($1) $2-$3');else if(v.length>2)v=v.replace(/(\d{2})(\d{1,5})/,'($1) $2');whatsappInput.value=v;}
            function mascCep(){var v=somenteDigitos(cepInput.value).slice(0,8);if(v.length>5)v=v.replace(/(\d{5})(\d{1,3})/,'$1-$2');cepInput.value=v;}
            function vNome(){var v=nomeInput.value.trim();if(!v){setError('nome','Digite seu nome completo.');return false;}if(v.length>50){setError('nome','M\u00e1ximo 50 caracteres.');return false;}if(!/^[A-Za-z\u00C0-\u00FF '\u00b4`^~.-]+$/.test(v)){setError('nome','Use apenas letras e sinais permitidos.');return false;}setError('nome','');return true;}
            function vGenero(){if(!generoInput.value){setError('genero','Selecione o g\u00eanero.');return false;}setError('genero','');return true;}
            function vCPF(){if(!validarCPF(cpfInput.value)){setError('cpf','CPF inv\u00e1lido.');return false;}setError('cpf','');return true;}
            function vNasc(){if(!idadePermitida(nascimentoInput.value)){setError('nascimento','Idade permitida: 16 a 90 anos.');return false;}setError('nascimento','');return true;}
            function vWpp(){var d=somenteDigitos(whatsappInput.value);if(d.length!==11||!/^\(\d{2}\) \d{5}-\d{4}$/.test(whatsappInput.value)||!validarDDD(whatsappInput.value)){setError('whatsapp','Informe um WhatsApp com DDD v\u00e1lido do Brasil.');return false;}setError('whatsapp','');return true;}
            function vCep(){if(!/^\d{5}-\d{3}$/.test(cepInput.value.trim())){setError('cep','CEP inv\u00e1lido. Formato: 00000-000.');return false;}setError('cep','');return true;}
            function vBairro(){var v=bairroInput.value.trim();if(!v){setError('bairro','Informe o bairro.');return false;}if(v.length>40){setError('bairro','M\u00e1ximo 40 caracteres.');return false;}setError('bairro','');return true;}
            function vEmail(){if(!validarEmail(emailInput.value)){setError('email','Digite um e-mail v\u00e1lido (Gmail, Hotmail, Outlook ou Yahoo).');return false;}setError('email','');return true;}
            function validarPassoDados(){var checks=[{ok:vNome(),f:nomeInput},{ok:vGenero(),f:generoInput},{ok:vCPF(),f:cpfInput},{ok:vNasc(),f:nascimentoInput},{ok:vWpp(),f:whatsappInput},{ok:vCep(),f:cepInput},{ok:vBairro(),f:bairroInput},{ok:vEmail(),f:emailInput}];var first=checks.find(function(c){return !c.ok;});if(first){first.f.focus();return false;}return true;}
            function validarPassoEscolher(){if(!turmaSelect.value&&!(cursoInput.value&&localInput.value)){setError('opcao_id','Selecione uma turma v\u00e1lida.');return false;}setError('opcao_id','');return true;}
            function validarPassoRevisao(){if(!confirmaDadosInput.checked){setError('confirma_dados','Confirme os dados para finalizar.');confirmaDadosInput.focus();return false;}setError('confirma_dados','');return true;}
            async function buscarBairro(){var limpo=somenteDigitos(cepInput.value);if(limpo.length!==8)return;try{var r=await fetch('https://viacep.com.br/ws/'+limpo+'/json/');var d=await r.json();if(!d.erro&&d.bairro){bairroInput.value=d.bairro;vBairro();syncReview();}}catch(e){console.error(e);}}
            document.querySelectorAll('[data-next]').forEach(function(btn){btn.addEventListener('click',function(){var t=btn.dataset.next;if(t==='escolher'&&!validarPassoDados())return;if(t==='revisao'&&!validarPassoEscolher())return;syncReview();mostrarPasso(t);});});
            document.querySelectorAll('[data-prev]').forEach(function(btn){btn.addEventListener('click',function(){syncReview();mostrarPasso(btn.dataset.prev);});});
            form.addEventListener('submit',function(e){if(!validarPassoDados()){e.preventDefault();mostrarPasso('dados');return;}syncReview();if(!validarPassoRevisao()){e.preventDefault();mostrarPasso('revisao');}});
            nomeInput.addEventListener('blur',vNome);generoInput.addEventListener('change',vGenero);
            cpfInput.addEventListener('input',function(){mascCPF();if(somenteDigitos(cpfInput.value).length===11)vCPF();else setError('cpf','');syncReview();});
            nascimentoInput.addEventListener('input',function(){mascNasc();syncReview();});nascimentoInput.addEventListener('blur',vNasc);
            whatsappInput.addEventListener('input',function(){mascWpp();if(somenteDigitos(whatsappInput.value).length>=10)vWpp();else setError('whatsapp','');syncReview();});
            cepInput.addEventListener('input',function(){mascCep();bairroInput.value='';if(cepInput.value.length===9){vCep();buscarBairro();}else setError('cep','');syncReview();});
            bairroInput.addEventListener('blur',function(){vBairro();syncReview();});
            emailInput.addEventListener('input',function(){if(emailInput.value.trim())vEmail();else setError('email','');syncReview();});
            confirmaDadosInput.addEventListener('change',function(){if(confirmaDadosInput.checked)setError('confirma_dados','');});
            cursoSelect.addEventListener('change',function(){atualizarLocais();syncReview();});
            localSelectEl.addEventListener('change',function(){atualizarTurmas();syncReview();});
            turmaSelect.addEventListener('change',function(){aplicarOpcaoCurso(turmaSelect.value);var h=document.getElementById('hidden_opcao_id');if(h)h.value=turmaSelect.value;syncReview();});
            ['nome','genero','whatsapp','cep','bairro','email','curso','turma','dias_aula','horario','data_inicio','encerramento','endereco_curso','como_conheceu'].forEach(function(id){var f=document.getElementById(id);if(f){f.addEventListener('input',syncReview);f.addEventListener('change',syncReview);}});
            if(btnCopiarEndereco&&enderecoInput){btnCopiarEndereco.addEventListener('click',function(){navigator.clipboard.writeText(enderecoInput.value).then(function(){btnCopiarEndereco.textContent='COPIADO \u2705';}).catch(function(){enderecoInput.select();document.execCommand('copy');btnCopiarEndereco.textContent='COPIADO \u2705';});setTimeout(function(){btnCopiarEndereco.textContent='Copiar &#128203;';},1200);});}
            var beneficios=document.querySelectorAll('.beneficio-item'),idxB=0;
            if(beneficios.length){setInterval(function(){beneficios.forEach(function(el,i){el.style.display=(i===idxB)?'inline-block':'none';});idxB=(idxB+1)%beneficios.length;},2500);}
            var selectedOptionId='{{ form_data.get("opcao_id", "") }}';
            if(selectedOptionId&&courseOptionsById[selectedOptionId]){var option=courseOptionsById[selectedOptionId];cursoSelect.value=option.curso_id;atualizarLocais();localSelectEl.value=option.local;atualizarTurmas();if(turmaSelectGroup.style.display!=='none'){turmaSelect.value=selectedOptionId;aplicarOpcaoCurso(selectedOptionId);}}
            syncReview();
            mostrarPasso(stepOrder.includes(startStep)?startStep:'index');
        });
    </script>
</body>
</html>
"""
TEMPLATE_CONFIRMACAO = r"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Mulheres do Corre 5</title>
    <link rel="stylesheet" href="/static/style.css">
    <link rel="stylesheet" href="/static/assistant.css">
    <link href="https://fonts.googleapis.com/css2?family=Wise:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        :root{--cor-principal:#912922;--cor-clara:#fcecea;--cor-texto:#3d1210;--sombra-card:0 18px 55px rgba(145,41,34,0.18);}
        body{min-height:100vh;margin:0;background:radial-gradient(circle at top left,rgba(145,41,34,0.15),transparent 32%),linear-gradient(140deg,#fff5f4 0%,#fff 55%,#fce0de 100%);font-family:'Wise',Arial,sans-serif;}
        .main-header{border-bottom:4px solid #912922;background:rgba(255,255,255,0.92);}
        .header-logos{display:flex;flex-direction:column;align-items:center;gap:10px;padding:10px 12px;}
        .header-logos img{max-width:min(88vw,280px);height:auto;}
        .confirm-page{width:min(680px,calc(100% - 16px));margin:0 auto;padding:10px 0 20px;text-align:center;}
        .wizard-progress{margin:12px auto 16px;padding:14px;border-radius:28px;background:rgba(255,255,255,0.9);box-shadow:0 12px 30px rgba(145,41,34,0.12);}
        .wizard-track{width:100%;height:14px;border-radius:999px;background:#fce0de;overflow:hidden;}
        .wizard-fill{width:100%;height:100%;background:linear-gradient(90deg,#912922 0%,#d4645b 100%);border-radius:999px;}
        .wizard-labels{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px;}
        .wizard-label{padding:10px 8px;border:1px solid #e8a09c;border-radius:16px;background:#fff;color:#7a2520;font-size:0.84rem;font-weight:700;text-align:center;}
        .wizard-label.ativo{border-color:#912922;background:#fcecea;color:#912922;}
        .confirm-shell{background:rgba(255,255,255,0.88);border:1px solid rgba(255,255,255,0.9);border-radius:30px;box-shadow:var(--sombra-card);overflow:hidden;text-align:center;}
        .confirm-card{padding:20px 16px 18px;max-width:620px;margin:0 auto;text-align:center;}
        .checkmark{width:120px;height:120px;margin:0 auto 12px;}
        .checkmark svg{width:100%;height:100%;stroke:#912922;fill:none;}
        .confirm-card h1{margin:0 0 10px;color:#912922;font-size:clamp(1.8rem,4vw,2.6rem);letter-spacing:-0.04em;}
        .protocol-box{margin:16px auto 12px;padding:14px;max-width:320px;border-radius:16px;background:#fcecea;border:2px solid #912922;}
        .protocol-box strong{display:block;color:#912922;font-size:0.98rem;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.04em;}
        .protocol-box span{display:block;color:#912922;font-size:1.35rem;font-weight:900;letter-spacing:0.08em;word-break:break-all;}
        .next-steps{margin:16px auto 0;max-width:460px;padding:14px;border-radius:18px;background:#fff;border:1px solid #f0c0bc;}
        .next-steps h2{margin:0 0 12px;color:#912922;font-size:1.2rem;}
        .next-steps ol{margin:0;padding-left:22px;color:#3d1210;line-height:1.55;list-style-position:inside;}
        .actions{display:grid;gap:10px;margin-top:16px;max-width:380px;margin-left:auto;margin-right:auto;}
        .action-button{display:flex;align-items:center;justify-content:center;min-height:42px;padding:10px 14px;border-radius:12px;text-decoration:none;text-transform:uppercase;font-weight:800;letter-spacing:0.03em;transition:transform 0.16s ease;}
        .action-button.primary{background:linear-gradient(90deg,#912922 0%,#d4645b 100%);color:#fff;box-shadow:0 10px 24px rgba(145,41,34,0.24);}
        .action-button.secondary{background:#fff;color:#912922;border:2px solid #912922;}
        .action-button:hover{transform:translateY(-1px);}
        @media(max-width:640px){
            html,body{width:100%!important;max-width:100%!important;overflow-x:hidden!important;}body*{min-width:0;}
            .confirm-page{width:calc(100% - 8px)!important;max-width:100%!important;padding:6px 0 12px;}.confirm-card{width:100%!important;max-width:100%!important;padding:14px 10px 12px;}
            .wizard-progress{width:100%!important;max-width:100%!important;padding:10px;border-radius:18px;}.wizard-labels{grid-template-columns:1fr;gap:6px;}
            .confirm-shell{width:100%!important;max-width:100%!important;border-radius:18px;}.protocol-box span{font-size:1.3rem;}
            .next-steps,.actions,.action-button,.protocol-box,.wizard-label,.wizard-track{width:100%!important;max-width:100%!important;}img,svg{max-width:100%!important;height:auto!important;}
        }
    </style>
</head>
<body>
    <script src="/static/assistant.js"></script>
    <header class="main-header">
        <div class="header-logos">
            <img src="/static/logo-prefeitura.png" alt="Prefeitura do Rio" class="logo-prefeitura-topo">
        </div>
    </header>
    <div class="confirm-page">
        <div class="wizard-progress">
            <div class="wizard-track"><div class="wizard-fill"></div></div>
            <div class="wizard-labels">
                <div class="wizard-label">1. Inicio</div>
                <div class="wizard-label">2. Dados pessoais</div>
                <div class="wizard-label">3. Escolher</div>
                <div class="wizard-label ativo">4. Confirma&#231;&#227;o</div>
            </div>
        </div>
        <div class="confirm-shell"><div class="confirm-card">
            <div class="checkmark"><svg viewBox="0 0 200 200"><circle cx="100" cy="100" r="90" stroke-width="16"></circle><polyline points="60,110 95,145 145,75" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"></polyline></svg></div>
            <h1>Inscri&#231;&#227;o realizada com sucesso</h1>
            <div class="protocol-box"><strong>N&#250;mero de protocolo</strong><span>{{ protocolo }}</span></div>
            <div class="actions">
                <a class="action-button primary" href="{{ whatsapp_share_url }}" target="_blank" rel="noopener noreferrer">Compartilhar no WhatsApp</a>
                <a class="action-button secondary" href="{{ url_for('home') }}">Voltar ao in&#237;cio</a>
            </div>
            <div class="next-steps"><h2>Pr&#243;ximos passos</h2><ol>
                <li>Aguarde nosso contato via WhatsApp.</li>
                <li>Prepare RG, CPF e comprovante de resid&#234;ncia.</li>
                <li>Fique atento ao contato com os detalhes da turma.</li>
                <li>Compare&#231;a &#224; unidade informada no dia marcado.</li>
            </ol></div>
        </div></div>
    </div>
</body>
</html>
"""
# =============================================================================
# APLICACAO FLASK
# =============================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "chave-secreta-para-sessao")

def get_default_form_data(source=None):
    form_data = {
        "nome": "", "genero": "", "cpf": "", "nascimento": "",
        "whatsapp": "", "cep": "", "bairro": "", "email": "",
        "opcao_id": "", "local": "", "curso": "", "turma": "",
        "dias_aula": "", "horario": "", "data_inicio": "",
        "encerramento": "", "endereco_curso": "",
        "como_conheceu": "", "confirma_dados": "",
    }
    if source:
        for key in form_data:
            value = source.get(key, form_data[key])
            if key == "confirma_dados":
                form_data[key] = "sim" if value else ""
            else:
                form_data[key] = (value or "").strip()
        selected_option = get_course_option(form_data["opcao_id"])
        if selected_option:
            fill_form_data_from_option(form_data, selected_option)
    return form_data

def cpf_valido(cpf):
    digits = re.sub(r"\D", "", cpf or "")
    if len(digits) != 11 or len(set(digits)) == 1: return False
    total = sum(int(digits[i]) * (10 - i) for i in range(9))
    digit = (total * 10) % 11; digit = 0 if digit == 10 else digit
    if digit != int(digits[9]): return False
    total = sum(int(digits[i]) * (11 - i) for i in range(10))
    digit = (total * 10) % 11; digit = 0 if digit == 10 else digit
    return digit == int(digits[10])

def idade_aceita(nascimento):
    try: dn = datetime.strptime(nascimento, "%d/%m/%Y")
    except ValueError: return False
    hoje = datetime.today(); idade = hoje.year - dn.year
    if (hoje.month, hoje.day) < (dn.month, dn.day): idade -= 1
    return 16 <= idade <= 90

def whatsapp_valido(whatsapp):
    digits = re.sub(r"\D", "", whatsapp or "")
    if len(digits) != 11: return False
    if not re.fullmatch(r"\(\d{2}\) \d{5}-\d{4}", whatsapp or ""): return False
    return digits[:2] in VALID_DDDS

def validate_form_data(form_data):
    errors = {}
    selected_option = get_course_option(form_data["opcao_id"])
    if not selected_option and form_data.get("curso") and form_data.get("local"):
        match = next((o for o in COURSE_OPTIONS
                      if o["curso"] == form_data["curso"] and o["local"] == form_data["local"]), None)
        if match:
            form_data["opcao_id"] = match["id"]
            selected_option = match
    if not selected_option:
        errors["opcao_id"] = "Selecione uma turma v\u00e1lida."
    nome = form_data["nome"]
    if not nome: errors["nome"] = "Digite seu nome completo."
    elif len(nome) > 50: errors["nome"] = "O nome deve ter no m\u00e1ximo 50 caracteres."
    elif not NAME_PATTERN.fullmatch(nome): errors["nome"] = "Use apenas letras e sinais permitidos no nome."
    if form_data["genero"] not in {"Feminino", "Masculino", "Outro", "Prefiro n\u00e3o dizer"}:
        errors["genero"] = "Selecione o g\u00eanero."
    if not cpf_valido(form_data["cpf"]): errors["cpf"] = "CPF inv\u00e1lido. Verifique e digite novamente."
    if not idade_aceita(form_data["nascimento"]): errors["nascimento"] = "Idade permitida: de 16 at\u00e9 90 anos."
    if not whatsapp_valido(form_data["whatsapp"]): errors["whatsapp"] = "Informe um WhatsApp com DDD v\u00e1lido do Brasil."
    if not re.fullmatch(r"\d{5}-\d{3}", form_data["cep"] or ""): errors["cep"] = "CEP inv\u00e1lido. Formato: 00000-000."
    bairro = form_data["bairro"]
    if not bairro: errors["bairro"] = "Informe o bairro."
    elif len(bairro) > 40: errors["bairro"] = "O bairro deve ter no m\u00e1ximo 40 caracteres."
    if not ALLOWED_EMAIL_PATTERN.fullmatch(form_data["email"] or ""):
        errors["email"] = "Digite um e-mail v\u00e1lido do Gmail, Hotmail, Outlook ou Yahoo."
    if form_data["confirma_dados"] != "sim":
        errors["confirma_dados"] = "Confirme os dados para finalizar a inscri\u00e7\u00e3o."
    return errors

def error_step(errors):
    if "confirma_dados" in errors: return "revisao"
    if "opcao_id" in errors: return "escolher"
    return "dados"

def render_wizard(form_data=None, errors=None, current_step="index"):
    current_form_data = form_data or get_default_form_data()
    selected_option   = get_course_option(current_form_data.get("opcao_id")) or COURSE_INFO
    curso_selecionado = selected_option.get("curso_id", "") if selected_option else ""
    return render_template_string(
        TEMPLATE_WIZARD,
        course_info        = selected_option,
        course_options     = COURSE_OPTIONS,
        cursos_disponiveis = CURSOS_DISPONIVEIS,
        curso_selecionado  = curso_selecionado,
        current_step       = current_step,
        errors             = errors or {},
        form_data          = current_form_data,
        generos            = ["Feminino", "Masculino", "Outro", "Prefiro n\u00e3o dizer"],
    )

@app.route("/", methods=["GET"])
def home(): return render_wizard()

@app.route("/inscricao", methods=["GET", "POST"])
def inscricao_unica():
    if request.method == "GET": return redirect(url_for("home"))
    form_data = get_default_form_data(request.form)
    errors    = validate_form_data(form_data)
    if errors: return render_wizard(form_data=form_data, errors=errors, current_step=error_step(errors))
    protocolo = str(uuid.uuid4())[:8].upper()
    session["protocolo"] = protocolo
    session.permanent = True
    dados = [
        protocolo,
        form_data["nome"], form_data["genero"], form_data["cpf"],
        form_data["nascimento"], form_data["whatsapp"], form_data["email"],
        form_data["cep"], form_data["bairro"], form_data["local"],
        form_data["curso"], form_data["turma"], form_data["dias_aula"],
        form_data["horario"], form_data["data_inicio"], form_data["encerramento"],
        form_data["endereco_curso"], form_data["como_conheceu"],
    ]
    try: append_to_sheet(dados)
    except Exception as exc: print("Erro ao salvar na planilha:", exc); traceback.print_exc()
    try:
        response = send_registration_to_supabase(form_data)
        print("Envio para Supabase concluido:", response.status_code)
    except Exception as exc: print("Erro ao enviar para Supabase:", exc)
    return redirect(url_for("confirmacao", protocolo=protocolo))

@app.route("/curso",   methods=["GET", "POST"])
@app.route("/revisao", methods=["GET", "POST"])
@app.route("/wizard",  methods=["GET"])
def legacy_routes(): return redirect(url_for("home"))

@app.route("/confirmacao", methods=["GET"])
@app.route("/confirmacao/<protocolo>", methods=["GET"])
def confirmacao(protocolo=None):
    if not protocolo:
        protocolo = session.get("protocolo")
    if not protocolo:
        return redirect(url_for("home"))
    return render_template_string(
        TEMPLATE_CONFIRMACAO,
        protocolo          = protocolo,
        whatsapp_share_url = build_whatsapp_share_url(),
    )

# =============================================================================
# SUPABASE
# =============================================================================
SUPABASE_FUNCTION_URL = os.environ.get(
    "SUPABASE_FUNCTION_URL",
    "https://egpyhfzatabyftwajoad.supabase.co/functions/v1/fgm-register",
)
SUPABASE_API_KEY = os.environ.get(
    "SUPABASE_API_KEY",
    "jyUskwXkc54ZcMPyADLFN6LvZO0I60e3",
)

def normalize_phone_number(phone):
    digits = re.sub(r"[^\d]", "", phone or "")
    return f"55{digits}" if len(digits) == 11 else digits

def send_registration_to_supabase(form_data):
    phone = normalize_phone_number(form_data.get("whatsapp", ""))
    payload = {
        "name":           form_data.get("nome", ""),
        "phone":          phone,
        "curso":          form_data.get("curso", ""),
        "local":          form_data.get("local", ""),
        "dia_semana":     form_data.get("dias_aula", ""),
        "dias_semana":    form_data.get("dias_aula", ""),
        "data_inicio":    form_data.get("data_inicio", ""),
        "data_inscricao": datetime.utcnow().isoformat() + "Z",
        "horario":        form_data.get("horario", ""),
    }
    headers = {
        "Content-Type":  "application/json",
        "Accept":        "application/json",
        "x-api-key":     SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
    }
    response = requests.post(SUPABASE_FUNCTION_URL, headers=headers, json=payload, timeout=10)
    if not response.ok:
        raise RuntimeError(f"Supabase retornou {response.status_code}: {response.text[:500]}")
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
