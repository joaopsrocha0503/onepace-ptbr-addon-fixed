import fs from "node:fs";
import path from "node:path";
import { describe, it, expect, beforeAll } from "vitest";

const SUBS_DIR = path.join(import.meta.dirname, "..", "subs");
const SUBS_BASE_URL = "https://example.baby-beamup.club/subs";
const MAPPING_PATH = path.join(SUBS_DIR, "mapping.json");

let mapping;

beforeAll(() => {
  mapping = JSON.parse(fs.readFileSync(MAPPING_PATH, "utf-8"));
});

// Espelha a extração do index.js: entradas podem ser string ou {srt, ass}
function srtOf(entry) {
  return typeof entry === "string" ? entry : entry.srt;
}

// Espelha index.js: os caminhos incluem a subpasta do arco, por isso a "/"
// não pode ser percent-encoded.
const encodePath = (p) => p.split("/").map(encodeURIComponent).join("/");

describe("mapping.json", () => {
  it("loads with at least one entry", () => {
    expect(Object.keys(mapping).length).toBeGreaterThan(0);
  });

  it("has valid episode ID format", () => {
    for (const key of Object.keys(mapping)) {
      expect(key).toMatch(/^[A-Z_]+_\d+$/);
    }
  });

  it("has .srt filenames as values", () => {
    for (const value of Object.values(mapping)) {
      expect(srtOf(value)).toMatch(/\.srt$/);
    }
  });

  it("stores paths under a numbered arc subfolder", () => {
    for (const value of Object.values(mapping)) {
      expect(srtOf(value)).toMatch(/^\d{2}_[A-Za-z0-9_]+\/[A-Z_]+_\d+\.srt$/);
    }
  });

  it("references existing SRT files", () => {
    for (const value of Object.values(mapping)) {
      const srtFile = srtOf(value);
      const fullPath = path.join(SUBS_DIR, srtFile);
      expect(fs.existsSync(fullPath), `Missing: ${srtFile}`).toBe(true);
    }
  });
});

describe("subtitle handler logic", () => {
  function getSubtitles(videoID) {
    if (Object.hasOwn(mapping, videoID)) {
      const srtFile = srtOf(mapping[videoID]);
      if (!srtFile) return [];
      return [
        {
          id: `onepace-ptbr-${videoID}`,
          url: `${SUBS_BASE_URL}/${encodePath(srtFile)}`,
          lang: "por",
        },
      ];
    }
    return [];
  }

  it("returns subtitle for known episode", () => {
    const result = getSubtitles("RO_1");
    expect(result).toHaveLength(1);
    expect(result[0].lang).toBe("por");
    expect(result[0].url).toContain("RO_1.srt");
  });

  it("returns empty for unknown episode", () => {
    expect(getSubtitles("NONEXISTENT_999")).toEqual([]);
  });

  it("builds correct URL", () => {
    const result = getSubtitles("RO_1");
    expect(result[0].url).toBe(`${SUBS_BASE_URL}/${srtOf(mapping.RO_1)}`);
  });

  // Espelha a rota de compatibilidade do index.js: até 2026-07-21 os .srt viviam
  // direto em /subs/<ficheiro>.srt e essas respostas ficam 4h em cache.
  it("maps every legacy flat filename back to its arc path", () => {
    const legacy = new Map();
    for (const entry of Object.values(mapping)) {
      const paths = typeof entry === "string" ? [entry] : [entry?.srt, entry?.ass];
      for (const relative of paths) {
        if (relative?.includes("/")) {
          legacy.set(relative.slice(relative.lastIndexOf("/") + 1), relative);
        }
      }
    }

    for (const value of Object.values(mapping)) {
      const srtFile = srtOf(value);
      const base = srtFile.slice(srtFile.lastIndexOf("/") + 1);
      expect(legacy.get(base), `sem redirect para ${base}`).toBe(srtFile);
    }
    expect(legacy.get("WC_15.srt")).toBe("33_Whole_Cake_Island/WC_15.srt");
  });

  it("does not percent-encode the arc subfolder separator", () => {
    const result = getSubtitles("WC_15");
    expect(result[0].url).not.toContain("%2F");
    expect(result[0].url).toContain("/33_Whole_Cake_Island/WC_15.srt");
  });
});
