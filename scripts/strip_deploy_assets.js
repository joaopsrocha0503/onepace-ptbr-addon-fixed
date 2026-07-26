/**
 * Remove os .ass de subs/ da árvore de build, antes de o slug ser fechado.
 *
 * Porquê: os .ass valem ~447 MB dos ~461 MB de subs/, mas o addon nunca os
 * oferece -- o handler em index.js só devolve a variante .srt, porque o
 * pipeline de legendas externas do Stremio só aceita .srt/.vtt
 * (stremio-bugs#2312). Iam parar à imagem sem nunca serem pedidos.
 *
 * Porquê aqui e não num ficheiro de exclusão: o .dockerignore é inerte (não há
 * Dockerfile, a Beamup usa buildpacks) e o .slugignore também -- o herokuish só
 * o lê em `slug-generate`, e o Dokku corre `buildpack-build`. O hook
 * `heroku-prebuild` do buildpack Node é o único ponto que corre mesmo.
 *
 * Só apaga com --yes. Sem a flag faz dry-run, para que correr o script à mão
 * nunca destrua os originais locais -- são a fonte de posicionamento do
 * scripts/fix_subtitle_positions.py e têm de ficar em git.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SUBS_DIR = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "subs"
);

const apply = process.argv.includes("--yes");

function collect(dir) {
  const found = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) found.push(...collect(full));
    else if (entry.name.endsWith(".ass")) found.push(full);
  }
  return found;
}

if (!fs.existsSync(SUBS_DIR)) {
  console.log("strip_deploy_assets: subs/ não existe, nada a fazer");
  process.exit(0);
}

const files = collect(SUBS_DIR);
const bytes = files.reduce((sum, f) => sum + fs.statSync(f).size, 0);
const mb = (bytes / 1024 / 1024).toFixed(1);

if (!apply) {
  console.log(
    `strip_deploy_assets: dry-run -- ${files.length} .ass (${mb} MB) seriam removidos. Usa --yes para apagar.`
  );
  process.exit(0);
}

for (const file of files) fs.rmSync(file);
console.log(`strip_deploy_assets: ${files.length} .ass removidos (${mb} MB)`);
