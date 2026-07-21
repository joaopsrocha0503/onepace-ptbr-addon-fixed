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

try {
  subtitleMap = JSON.parse(
    fs.readFileSync(path.join(SUBS_DIR, "mapping.json"), "utf-8")
  );
  console.log(`📂 ${Object.keys(subtitleMap).length} legendas PT-BR carregadas`);
} catch (e) {
  console.error("❌ Erro ao carregar mapping.json:", e.message);
}

// Base pública por request (ex.: https://xyz.baby-beamup.club), capturada por
// middleware — os URLs das legendas têm de ser absolutos e o host só se sabe
// na altura do pedido.
const requestBase = new AsyncLocalStorage();

const PUBLIC_URL =
  process.env.PUBLIC_URL ||
  "https://e4872e87374f-onepace-ptbr-addon.baby-beamup.club";

const manifest = {
  id: "community.onepace.ptbr.subs.fixed",
  version: pkg.version,
  name: "One Pace PT-BR Subs (Fixed)",
  description:
    "Legendas em Português do Brasil para o One Pace, corrigidas e sincronizadas. Fork do addon de rafaelmotac com legendas revistas.",
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
app.get("/logo.png", (req, res) => res.sendFile(path.join(__dirname, "logo.png")));
app.get("/", (req, res) => res.redirect("/manifest.json"));
app.use(getRouter(builder.getInterface()));

const server = app
  .listen(PORT, () => {
    console.log(`\n🏴‍☠️ One Pace PT-BR Subs Addon`);
    console.log(`   Manifest: http://127.0.0.1:${PORT}/manifest.json`);
    console.log(`   Legendas: http://127.0.0.1:${PORT}/subs/<ficheiro>.srt`);
    console.log(`\n📋 ${Object.keys(subtitleMap).length} episódios com legenda PT-BR`);
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
