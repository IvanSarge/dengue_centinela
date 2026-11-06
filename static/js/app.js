/* Centinela Analytics · DengueCheck Pediátrico — lógica del cliente */
(() => {
  "use strict";

  const META = JSON.parse(document.getElementById("meta-json").textContent);
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const NOM = { logistica: "Regresión logística", rna: "Red neuronal artificial" };
  const COL = { logistica: "#14A3A0", rna: "#F26B4E" };
  const NIVEL_COL = { bajo: "#2E9E6B", moderado: "#E8A020", alto: "#D8453A" };

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dec = (x, d = 2) => Number(x).toFixed(d).replace(".", ",");
  const pct = (x, d = 1) => dec(x * 100, d) + " %";
  const miles = (x) => Number(x).toLocaleString("es-CO");

  /* ------------------------------------------------------------------ */
  /* Navegación                                                          */
  /* ------------------------------------------------------------------ */
  const burger = $("#burger"), nav = $("#nav");
  burger.addEventListener("click", () => {
    const abierto = nav.classList.toggle("is-open");
    burger.setAttribute("aria-expanded", abierto);
  });
  $$("#nav a").forEach((a) => a.addEventListener("click", () => { nav.classList.remove("is-open"); burger.setAttribute("aria-expanded", "false"); }));

  const enlaces = $$('#nav a[href^="#"]:not(.btn)');
  if ("IntersectionObserver" in window) {
    const obs = new IntersectionObserver((entradas) => {
      entradas.forEach((e) => {
        if (e.isIntersecting) enlaces.forEach((a) => a.classList.toggle("is-active", a.getAttribute("href") === "#" + e.target.id));
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    $$("main section[id]").forEach((s) => obs.observe(s));

    const rev = new IntersectionObserver((entradas) => entradas.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("is-in"); rev.unobserve(e.target); }
    }), { threshold: 0.08 });
    $$(".card:not(.result), .section__head, .metric").forEach((el) => { el.classList.add("reveal"); rev.observe(el); });
  }

  /* ------------------------------------------------------------------ */
  /* Estadísticas del hero                                               */
  /* ------------------------------------------------------------------ */
  const M = META.modelos;
  const stats = {
    n_pacientes: META.n_pacientes, n_variables: META.n_variables,
    auc_log: dec(M.logistica.auc_cv_media), auc_rna: dec(M.rna.auc_cv_media),
  };
  $$("[data-stat]").forEach((el) => { el.textContent = stats[el.dataset.stat]; });

  /* ------------------------------------------------------------------ */
  /* Formulario                                                          */
  /* ------------------------------------------------------------------ */
  const form = $("#formulario");
  const EJEMPLOS = {
    leve: { edad_mayor_6: 1, sexo_masculino: 1, duracion_fiebre: 3, cefalea: 1, mialgia: 1, dolor_abdominal: 0, exantema: 0, vomito: 0, disnea: 0, sangrado: 0, hipotension: 0, organomegalia: 0, hemoglobina: 12.5, pcv: 37, plaquetas: 160000, alt: 25, leuco_min: 3800, leuco_max: 4500, creatinina: 0.5 },
    medio: { edad_mayor_6: 1, sexo_masculino: 0, duracion_fiebre: 5, cefalea: 0, mialgia: 0, dolor_abdominal: 0, exantema: 0, vomito: 1, disnea: 0, sangrado: 0, hipotension: 0, organomegalia: 0, hemoglobina: 13.5, pcv: 42, plaquetas: 70000, alt: 45, leuco_min: 3000, leuco_max: 7200, creatinina: 0.5 },
    grave: { edad_mayor_6: 1, sexo_masculino: 0, duracion_fiebre: 6, cefalea: 0, mialgia: 0, dolor_abdominal: 1, exantema: 0, vomito: 1, disnea: 0, sangrado: 1, hipotension: 1, organomegalia: 1, hemoglobina: 15.5, pcv: 46, plaquetas: 40000, alt: 180, leuco_min: 4000, leuco_max: 9500, creatinina: 0.8 },
  };
  const BIN = ["edad_mayor_6", "sexo_masculino", "cefalea", "mialgia", "dolor_abdominal", "exantema", "vomito", "disnea", "sangrado", "hipotension", "organomegalia"];
  const SELECTS = ["edad_mayor_6", "sexo_masculino"];
  const NUMS = {
    duracion_fiebre: [1, 20, "Duración de la fiebre"], hemoglobina: [4, 25, "Hemoglobina"], pcv: [12, 70, "Hematocrito (PCV)"],
    plaquetas: [1000, 900000, "Plaquetas"], alt: [1, 6000, "ALT"], leuco_min: [300, 60000, "Leucocitos mínimos"],
    leuco_max: [300, 60000, "Leucocitos máximos"], creatinina: [0.05, 15, "Creatinina"],
  };

  function cargarEjemplo(nombre) {
    const e = EJEMPLOS[nombre];
    Object.entries(e).forEach(([k, v]) => {
      const el = form.elements[k];
      if (!el) return;
      if (el.type === "checkbox") el.checked = !!v; else el.value = String(v);
    });
    $$(".is-invalid", form).forEach((x) => x.classList.remove("is-invalid"));
    $("#errores").hidden = true;
    enviar();
  }
  $$("[data-ejemplo]").forEach((b) => b.addEventListener("click", () => cargarEjemplo(b.dataset.ejemplo)));
  $("#btnLimpiar").addEventListener("click", () => {
    form.reset(); ultimo = null;
    $("#resultadoCuerpo").hidden = true; $("#resultadoVacio").hidden = false; $("#errores").hidden = true;
    $$(".is-invalid", form).forEach((x) => x.classList.remove("is-invalid"));
  });

  function recolectar() {
    const datos = {}, errores = [];
    $$(".is-invalid", form).forEach((x) => x.classList.remove("is-invalid"));
    BIN.forEach((c) => {
      const el = form.elements[c];
      if (SELECTS.includes(c)) {
        if (el.value === "") { errores.push(`Seleccione ${c === "edad_mayor_6" ? "el grupo de edad" : "el sexo"}.`); el.closest(".field").classList.add("is-invalid"); }
        else datos[c] = Number(el.value);
      } else datos[c] = el.checked ? 1 : 0;
    });
    Object.entries(NUMS).forEach(([c, [lo, hi, etiqueta]]) => {
      const el = form.elements[c];
      const v = parseFloat(String(el.value).replace(",", "."));
      if (el.value === "" || Number.isNaN(v)) { errores.push(`${etiqueta}: ingrese un valor.`); el.closest(".field").classList.add("is-invalid"); }
      else if (v < lo || v > hi) { errores.push(`${etiqueta}: debe estar entre ${miles(lo)} y ${miles(hi)}.`); el.closest(".field").classList.add("is-invalid"); }
      else datos[c] = v;
    });
    if (datos.leuco_min !== undefined && datos.leuco_max !== undefined && datos.leuco_max < datos.leuco_min) {
      errores.push("Los leucocitos máximos no pueden ser menores que los mínimos.");
      form.elements.leuco_max.closest(".field").classList.add("is-invalid");
    }
    return { datos, errores };
  }

  function mostrarErrores(lista) {
    const box = $("#errores");
    if (!lista.length) { box.hidden = true; return; }
    box.hidden = false;
    box.innerHTML = `<strong>Revise estos datos:</strong><ul>${lista.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>`;
  }

  let ultimo = null;
  async function enviar() {
    const { datos, errores } = recolectar();
    mostrarErrores(errores);
    if (errores.length) return;
    const btn = $("#btnEvaluar");
    btn.classList.add("is-loading"); btn.disabled = true;
    try {
      const r = await fetch("/api/predecir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) });
      const j = await r.json();
      if (!j.ok) { mostrarErrores(j.errores || ["No se pudo procesar la solicitud."]); return; }
      ultimo = j; renderResultado();
      if (window.matchMedia("(max-width: 1020px)").matches) $("#resultado").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      mostrarErrores(["No se pudo conectar con el servidor. Verifique que la aplicación esté en ejecución."]);
    } finally { btn.classList.remove("is-loading"); btn.disabled = false; }
  }
  form.addEventListener("submit", (e) => { e.preventDefault(); enviar(); });
  $$('input[name="modelo"]').forEach((r) => r.addEventListener("change", () => ultimo && renderResultado()));

  /* ---------- Resultado ---------- */
  function gauge(prob, umbral, nivel) {
    const cx = 120, cy = 120, r = 96;
    const ang = Math.PI * (1 - umbral / 100);
    const x1 = cx + (r - 14) * Math.cos(ang), y1 = cy - (r - 14) * Math.sin(ang);
    const x2 = cx + (r + 14) * Math.cos(ang), y2 = cy - (r + 14) * Math.sin(ang);
    const tx = cx + (r + 24) * Math.cos(ang), ty = cy - (r + 24) * Math.sin(ang);
    const path = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
    return `<svg viewBox="-6 -8 252 150" role="img" aria-label="Probabilidad ${dec(prob, 1)} por ciento">
      <path d="${path}" fill="none" stroke="#E6EDF3" stroke-width="18" stroke-linecap="round"/>
      <path class="arc" d="${path}" pathLength="100" fill="none" stroke="${NIVEL_COL[nivel]}" stroke-width="18" stroke-linecap="round" stroke-dasharray="0 100" data-v="${prob}"/>
      <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#12263A" stroke-width="2.5"/>
      <text x="${tx}" y="${ty + 3}" font-size="9" font-weight="700" fill="#12263A" text-anchor="middle" font-family="Plus Jakarta Sans, sans-serif">corte</text>
    </svg>`;
  }

  function renderResultado() {
    const sel = $('input[name="modelo"]:checked').value;
    const otro = sel === "logistica" ? "rna" : "logistica";
    const R = ultimo.resultados, a = R[sel], b = R[otro];

    const maxImp = Math.max(1, ...a.factores.map((f) => Math.abs(f.impacto)));
    const factores = a.factores.length ? a.factores.map((f) => {
      const w = Math.abs(f.impacto) / maxImp * 50, pos = f.impacto > 0;
      return `<div class="fact"><span>${esc(f.etiqueta)}</span>
        <div class="fact__bar"><i style="${pos ? `left:50%` : `left:${50 - w}%`};width:${w}%;background:${pos ? "var(--red)" : "var(--green)"}"></i></div>
        <b class="${pos ? "up" : "down"}">${pos ? "+" : "−"}${dec(Math.abs(f.impacto), 1)}</b></div>`;
    }).join("") : `<p class="muted">Ningún dato individual cambia de forma apreciable la estimación.</p>`;

    const acuerdo = ultimo.modelos_coinciden
      ? `Ambos modelos coinciden: ${a.complicado ? "<strong>riesgo de complicaciones</strong>" : "<strong>sin señales de complicación</strong>"}.`
      : `<strong>Los modelos discrepan</strong> (uno supera su punto de corte y el otro no). Interprete con cautela y apóyese en el criterio clínico.`;

    $("#resultadoVacio").hidden = true;
    const cuerpo = $("#resultadoCuerpo");
    cuerpo.hidden = false;
    cuerpo.innerHTML = `
      <div class="result__model"><span>${esc(a.nombre)}</span><span class="badge badge--${a.nivel}">${esc(a.nivel_texto)}</span></div>
      <div class="gauge">${gauge(a.probabilidad, a.umbral, a.nivel)}
        <div class="gauge__val"><b>${dec(a.probabilidad, 1)} %</b><span>probabilidad de complicaciones</span></div></div>
      <p class="result__msg">El punto de corte de este modelo es <strong>${dec(a.umbral, 1)} %</strong>. ${a.complicado ? "La estimación lo supera." : "La estimación queda por debajo."}</p>

      <div class="result__sec"><h4>Comparación de modelos</h4>
        <div class="cmp-models">
          <div class="is-sel">${esc(a.nombre)}<b>${dec(a.probabilidad, 1)} %</b><em>${esc(a.nivel_texto)}</em></div>
          <div>${esc(b.nombre)}<b>${dec(b.probabilidad, 1)} %</b><em>${esc(b.nivel_texto)}</em></div>
        </div>
        <div class="agree">${acuerdo}</div>
      </div>

      <div class="result__sec"><h4>Datos que más influyen <span style="text-transform:none;letter-spacing:0">(puntos porcentuales)</span></h4>${factores}</div>

      <div class="result__sec"><h4>Puntaje clínico del estudio original</h4>
        <div class="score-line"><b>${ultimo.puntaje_estudio}</b><span>de 7 puntos · ${ultimo.puntaje_alto ? "<strong>≥ 2: sugiere mayor riesgo</strong>" : "&lt; 2: riesgo bajo según el puntaje"}</span></div>
      </div>

      <div class="result__sec"><div class="reco reco--${a.nivel}">${esc(a.recomendacion)}</div></div>`;

    requestAnimationFrame(() => requestAnimationFrame(() => {
      const arc = $(".arc", cuerpo); if (arc) arc.setAttribute("stroke-dasharray", `${arc.dataset.v} 100`);
    }));
  }

})();
