import sdk from "stremio-addon-sdk";
import express from "express";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AsyncLocalStorage } from "node:async_hooks";

const { addonBuilder, getRouter } = sdk;

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const pkg = JSON.parse(
  fs.readFileSync(path.join(__dirname, "package.json"), "utf-8")
);

const SUBS_DIR = path.join(__dirname, "subs");

// Os caminhos em mapping.json incluem a subpasta do arco
// (ex.: "33_Whole_Cake_Island/WC_15.srt"). encodeURIComponent sozinho
// converteria a "/" em %2F e partia o URL -- codificar segmento a segmento.
const encodePath = (p) => p.split("/").map(encodeURIComponent).join("/");
let subtitleMap = {};

// Nome do ficheiro -> caminho relativo com a subpasta do arco. Preenchido a
// partir do mapping.json; serve a rota de compatibilidade no fim deste ficheiro.
const legacySubtitlePaths = new Map();

try {
  subtitleMap = JSON.parse(
    fs.readFileSync(path.join(SUBS_DIR, "mapping.json"), "utf-8")
  );
  for (const entry of Object.values(subtitleMap)) {
    const paths = typeof entry === "string" ? [entry] : [entry?.srt, entry?.ass];
    for (const relative of paths) {
      if (relative?.includes("/")) {
        legacySubtitlePaths.set(relative.slice(relative.lastIndexOf("/") + 1), relative);
      }
    }
  }
  console.log(`📂 ${Object.keys(subtitleMap).length} legendas carregadas`);
} catch (e) {
  console.error("❌ Erro ao carregar mapping.json:", e.message);
}

// Base pública por request (ex.: https://xyz.baby-beamup.club), capturada por
// middleware — os URLs das legendas têm de ser absolutos e o host só se sabe
// na altura do pedido.
const requestBase = new AsyncLocalStorage();

const PUBLIC_URL =
  process.env.PUBLIC_URL ||
  // Definida automaticamente pelo Render em todos os web services -- evita ter
  // de fixar o hostname à mão (o nome pode ganhar sufixo se "onepace-ptbr-addon"
  // já estiver ocupado por outra conta).
  process.env.RENDER_EXTERNAL_URL ||
  "https://e4872e87374f-onepace-ptbr-addon.baby-beamup.club";

const manifest = {
  // O id mantém "ptbr" de propósito, apesar de os arcos 33-37 já serem PT-PT:
  // o Stremio identifica o addon por este campo, e mudá-lo faria com que
  // quem já o tem instalado passasse a ver um addon diferente. É identidade,
  // não descrição -- a língua vive no name/description abaixo.
  id: "community.onepace.ptbr.subs.fixed",
  version: pkg.version,
  name: "One Pace Legendas PT (Fixed)",
  description:
    "Legendas em português para o One Pace, corrigidas e sincronizadas. Arcos 1-32 em PT-BR; de Whole Cake Island a Egghead adaptados a PT-PT. Fork do addon de rafaelmotac com legendas revistas.",
  logo: `${PUBLIC_URL}/logo.png`,
  resources: [{ name: "subtitles", types: ["series"] }],
  types: ["series"],
  catalogs: [],
};

const builder = new addonBuilder(manifest);

builder.defineSubtitlesHandler(async ({ type, id, extra }) => {
  const videoID = extra?.videoID || id;

  console.log(`🔍 Request: type=${type} id=${id} videoID=${videoID}`);

  if (Object.hasOwn(subtitleMap, videoID)) {
    const entry = subtitleMap[videoID];
    const srtFile = typeof entry === "string" ? entry : entry.srt;
    const subtitles = [];

    // SUBS_BASE_URL (env) tem prioridade; sem ela, os .srt são servidos pelo
    // próprio addon em /subs.
    const baseUrl = process.env.SUBS_BASE_URL || `${requestBase.getStore()}/subs`;

    // Only the .srt variant is offered. Stremio's external-subtitle pipeline
    // accepts only .srt/.vtt, so .ass/.ssa external subs from an addon always
    // fail to load ("Failed to load external subtitles", stremio-bugs#2312) --
    // offering the .ass variant just shows an option that never works.
    if (srtFile) {
      subtitles.push({
        // Prefixo mantido por compatibilidade: é por este id que o Stremio
        // guarda a legenda escolhida por episódio. Renomeá-lo perdia a escolha.
        id: `onepace-ptbr-${videoID}`,
        url: `${baseUrl}/${encodePath(srtFile)}`,
        lang: "por",
      });
    }

    console.log(`  ✅ ${videoID} → ${subtitles.length} opções`);

    return { subtitles };
  }

  return { subtitles: [] };
});

const PORT = process.env.PORT || 7000;

const app = express();
app.set("trust proxy", true);

app.use((req, res, next) => {
  // O proxy interno da Beamup reescreve Host para o nome do serviço (sem
  // domínio); X-Forwarded-Host preserva o host original quando presente.
  const host = req.get("x-forwarded-host") || req.get("host");
  requestBase.run(`${req.protocol}://${host}`, next);
});

app.use("/subs", express.static(SUBS_DIR));

// Compatibilidade com os caminhos planos anteriores a 2026-07-21, quando subs/
// passou a estar organizada em subpastas por arco. As respostas do addon ficam
// 4h em cache no Cloudflare, por isso um cliente pode continuar a pedir
// /subs/WC_15.srt durante esse tempo -- redirecionar em vez de dar 404.
// Só apanha um segmento, logo nunca colide com /subs/<arco>/<ficheiro>.
app.get("/subs/:file", (req, res, next) => {
  const target = legacySubtitlePaths.get(req.params.file);
  if (!target) return next();
  res.redirect(302, `/subs/${encodePath(target)}`);
});
app.get("/logo.png", (req, res) => res.sendFile(path.join(__dirname, "logo.png")));
app.get("/", (req, res) => res.redirect("/manifest.json"));
app.use(getRouter(builder.getInterface()));

const server = app
  .listen(PORT, () => {
    console.log(`\n🏴‍☠️ One Pace Legendas PT (Fixed)`);
    console.log(`   Manifest: http://127.0.0.1:${PORT}/manifest.json`);
    console.log(`   Legendas: http://127.0.0.1:${PORT}/subs/<arco>/<ficheiro>.srt`);
    console.log(`\n📋 ${Object.keys(subtitleMap).length} episódios com legenda`);
  })
  .on("error", (err) => {
    console.error(`❌ Falha ao iniciar servidor na porta ${PORT}:`, err.message);
    process.exit(1);
  });

const shutdown = () => {
  console.log("\n🛑 Encerrando servidor...");
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
};

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
