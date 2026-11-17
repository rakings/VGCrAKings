package com.rakings.vgc;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Il quadrato diviso in diagonale (come in testata sul sito e nei post): VR celeste + Regionale giallo, scritte nere.
 *  Con un solo torneo: parte nera con le scritte e angolo colorato. Ogni riga di testo resta DENTRO il suo triangolo:
 *  se non ci sta, il testo si rimpicciolisce o va a capo. */
final class Disegno {
    static final int NERO = Color.parseColor("#140C12"), CELESTE = Color.parseColor("#86D8F0"), GIALLO = Color.parseColor("#FFD21F"),
            ROSSO = Color.parseColor("#E11D2E"), BIANCO = Color.WHITE;
    private static Typeface font;

    private static Typeface font(Context c) {
        if (font == null) {
            try { font = Typeface.create(Typeface.createFromAsset(c.getAssets(), "bric.ttf"), Typeface.BOLD); }
            catch (Exception e) { font = Typeface.DEFAULT_BOLD; }
        }
        return font;
    }

    static String etichetta(Context c, JSONObject e) {
        switch (e.optString("k")) {
            case "vr": return c.getString(R.string.vr);
            case "int": return c.getString(R.string.intl);
            case "ww": return c.getString(R.string.ww);
            case "sp": return c.getString(R.string.sp);
            default: return c.getString(R.string.reg);
        }
    }

    /** una riga da disegnare */
    private static final class Riga {
        String t; float size; int col; boolean live;
        Riga(String t, float size, int col) { this.t = t; this.size = size; this.col = col; }
    }

    static Bitmap quadrato(Context c, int lato, JSONObject vr, JSONObject rg, boolean liveVr, boolean liveRg) {
        lato = Math.max(120, Math.min(lato, 640));
        Bitmap b = Bitmap.createBitmap(lato, lato, Bitmap.Config.ARGB_8888);
        Canvas k = new Canvas(b);
        float r = lato * 0.12f, bordo = Math.max(3f, lato * 0.014f);
        Path forma = new Path();
        forma.addRoundRect(new RectF(0, 0, lato, lato), r, r, Path.Direction.CW);
        k.save();
        k.clipPath(forma);
        boolean due = vr != null && rg != null;
        JSONObject uno = due ? null : (vr != null ? vr : rg);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        // sfondo + triangolo in basso a destra
        p.setColor(due ? CELESTE : NERO);
        k.drawRect(0, 0, lato, lato, p);
        Path tri = new Path();
        tri.moveTo(lato, 0); tri.lineTo(lato, lato); tri.lineTo(0, lato); tri.close();
        p.setColor(due ? GIALLO : (uno == vr ? CELESTE : GIALLO));
        k.drawPath(tri, p);
        // diagonale bianca
        p.setColor(BIANCO);
        p.setStrokeWidth(Math.max(2f, lato * 0.012f));
        k.drawLine(0, lato, lato, 0, p);
        float pad = lato * 0.075f;
        if (due) {
            blocco(c, k, lato, pad, true, vr, liveVr, NERO, NERO);
            blocco(c, k, lato, pad, false, rg, liveRg, NERO, NERO);
        } else if (uno != null) {
            blocco(c, k, lato, pad, true, uno, uno == vr ? liveVr : liveRg, BIANCO, uno == vr ? CELESTE : GIALLO);
        }
        k.restore();
        // contorno nero
        Paint s = new Paint(Paint.ANTI_ALIAS_FLAG);
        s.setStyle(Paint.Style.STROKE);
        s.setStrokeWidth(bordo);
        s.setColor(Color.BLACK);
        k.drawRoundRect(new RectF(bordo / 2, bordo / 2, lato - bordo / 2, lato - bordo / 2), r, r, s);
        return b;
    }

    /** sopra = triangolo in alto a sinistra (testo allineato a sinistra), altrimenti in basso a destra (allineato a destra) */
    private static void blocco(Context c, Canvas k, int L, float pad, boolean sopra, JSONObject e, boolean live, int colTesto, int colEtichetta) {
        String lab = etichetta(c, e).toUpperCase(java.util.Locale.getDefault());
        String nome = e.optString("n");
        String data = Testo.intervallo(e.optString("d"), e.optString("e"));
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setTypeface(font(c));
        for (float scala = 1f; scala > 0.45f; scala -= 0.05f) {
            float sLab = L * 0.062f * scala, sNome = L * 0.098f * scala, sData = L * 0.066f * scala, sLive = L * 0.055f * scala;
            List<Riga> righe = new ArrayList<>();
            righe.add(new Riga(lab, sLab, colEtichetta));
            for (String x : aCapo(p, nome, sNome, L * 0.78f, 2)) righe.add(new Riga(x, sNome, colTesto));
            righe.add(new Riga(data, sData, colTesto));
            if (live) { Riga lr = new Riga("LIVE", sLive, BIANCO); lr.live = true; righe.add(lr); }
            if (disponi(k, p, L, pad, sopra, righe, false)) { disponi(k, p, L, pad, sopra, righe, true); return; }
        }
    }

    /** Prova a disporre le righe: ogni riga deve stare tutta nel suo triangolo. disegna=false solo controlla. */
    private static boolean disponi(Canvas k, Paint p, int L, float pad, boolean sopra, List<Riga> righe, boolean disegna) {
        float alt = 0;
        for (Riga x : righe) alt += altezza(x);
        float y = sopra ? pad : L - pad - alt;
        if (y < pad * 0.6f) return false;
        for (Riga x : righe) {
            p.setTextSize(x.size);
            float w = p.measureText(x.t) + (x.live ? x.size * 1.9f : 0);
            float top = y, bot = y + altezza(x);
            if (sopra) {
                // lato destro della riga a sinistra della diagonale, anche in fondo alla riga
                float maxX = L * (1f - bot / L) - pad * 0.7f;
                if (pad + w > maxX) return false;
                if (disegna) riga(k, p, x, pad, top, false);
            } else {
                float minX = L * (1f - top / L) + pad * 0.7f;
                if (L - pad - w < minX) return false;
                if (disegna) riga(k, p, x, L - pad, top, true);
            }
            y = bot;
        }
        return true;
    }

    private static float altezza(Riga x) { return x.size * (x.live ? 1.75f : 1.22f); }

    private static void riga(Canvas k, Paint p, Riga x, float xx, float top, boolean destra) {
        p.setTextSize(x.size);
        float w = p.measureText(x.t);
        if (x.live) {
            float pw = w + x.size * 1.9f, ph = x.size * 1.45f, x0 = destra ? xx - pw : xx, y0 = top + x.size * 0.2f;
            Paint f = new Paint(Paint.ANTI_ALIAS_FLAG);
            f.setColor(ROSSO);
            k.drawRoundRect(new RectF(x0, y0, x0 + pw, y0 + ph), ph / 2, ph / 2, f);
            f.setColor(BIANCO);
            k.drawCircle(x0 + x.size * 0.75f, y0 + ph / 2, x.size * 0.28f, f);
            p.setColor(BIANCO);
            p.setTextAlign(Paint.Align.LEFT);
            k.drawText(x.t, x0 + x.size * 1.3f, y0 + ph / 2 - (p.ascent() + p.descent()) / 2, p);
            return;
        }
        p.setColor(x.col);
        p.setTextAlign(destra ? Paint.Align.RIGHT : Paint.Align.LEFT);
        k.drawText(x.t, xx, top - p.ascent(), p);
    }

    /** va a capo sulle parole, al massimo «max» righe (l'ultima con «…» se serve) */
    private static List<String> aCapo(Paint p, String t, float size, float larg, int max) {
        p.setTextSize(size);
        List<String> out = new ArrayList<>();
        String[] parole = t.split("\\s+");
        StringBuilder cur = new StringBuilder();
        for (String w : parole) {
            String prova = cur.length() == 0 ? w : cur + " " + w;
            if (p.measureText(prova) <= larg || cur.length() == 0) { cur = new StringBuilder(prova); continue; }
            out.add(cur.toString());
            cur = new StringBuilder(w);
        }
        if (cur.length() > 0) out.add(cur.toString());
        if (out.size() > max) {
            List<String> o = new ArrayList<>(out.subList(0, max));
            o.set(max - 1, o.get(max - 1) + "…");
            return o;
        }
        return out;
    }
}
