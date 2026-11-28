package com.rakings.vgc;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;

import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Locale;

/** Disegno del widget Calendario: un'immagine sola (testata con il mese, giorni della settimana, griglia con i pallini dei tornei,
 *  legenda). Le proporzioni (PX, PT, TESTA, SETT, LEG, PB) sono le stesse dei layout w_cal_*.xml, cosi' le zone da toccare
 *  cadono esattamente sui giorni. */
final class DisegnoCal {
    static final float PX = 0.03f, PT = 0.03f, TESTA = 0.115f, SETT = 0.06f, LEG = 0.12f, PB = 0.03f;

    /** lettere dei tipi (come in widget.json) nell'ordine della legenda del sito */
    static final String ORDINE = "omvgrsiw";
    /** questi non si possono spegnere: Money, Victory Road, Regionali (altrimenti il calendario risulta troppo vuoto) */
    static final String FISSI = "mvr";
    static final int[] COLORI = {0xFFB794FF, 0xFFFF7A00, 0xFF86D8F0, 0xFFFFFFFF, 0xFFF59E0B, 0xFFFFD21F, 0xFF3DDC97, 0xFF000000};
    static final int[] NOMI = {R.string.cal_on, R.string.cal_mo, R.string.cal_vr, R.string.cal_gc, R.string.cal_rg, R.string.cal_sp, R.string.cal_in, R.string.cal_ww};

    private static Typeface font;

    private static Typeface font(Context c) {
        if (font == null) {
            try { font = Typeface.create(Typeface.createFromAsset(c.getAssets(), "bric.ttf"), Typeface.BOLD); }
            catch (Exception e) { font = Typeface.DEFAULT_BOLD; }
        }
        return font;
    }

    /** primo giorno della griglia: quante caselle vuote prima dell'1 */
    static int vuote(int anno, int mese, boolean lunedi) {
        Calendar k = Calendar.getInstance();
        k.clear();
        k.set(anno, mese, 1);
        int dow = k.get(Calendar.DAY_OF_WEEK);   // 1 = domenica
        return lunedi ? (dow + 5) % 7 : dow - 1;
    }

    static int giorniMese(int anno, int mese) {
        Calendar k = Calendar.getInstance();
        k.clear();
        k.set(anno, mese, 1);
        return k.getActualMaximum(Calendar.DAY_OF_MONTH);
    }

    static int settimane(int anno, int mese, boolean lunedi) {
        return (vuote(anno, mese, lunedi) + giorniMese(anno, mese) + 6) / 7;
    }

    static String iso(int anno, int mese, int giorno) {
        return String.format(Locale.US, "%04d-%02d-%02d", anno, mese + 1, giorno);
    }

    /** tipi visibili: tutti tranne quelli spenti nelle impostazioni (i FISSI restano sempre) */
    static String visibili(String spenti) {
        StringBuilder s = new StringBuilder();
        for (char x : ORDINE.toCharArray()) if (FISSI.indexOf(x) >= 0 || spenti == null || spenti.indexOf(x) < 0) s.append(x);
        return s.toString();
    }

    static Bitmap disegna(Context c, int W, int H, float sc, Tema t, int anno, int mese, boolean lunedi, String spenti,
                          boolean legenda, JSONObject cal, String oggi, boolean live) {
        Bitmap b = Bitmap.createBitmap(W, H, Bitmap.Config.ARGB_8888);
        Canvas k = new Canvas(b);
        // sfondo: lo stesso del tema scelto, con la trasparenza delle impostazioni
        try {
            Drawable d = c.getResources().getDrawable(t.fondo, null).mutate();
            d.setBounds(0, 0, W, H);
            d.setAlpha(t.alfa);
            d.draw(k);
        } catch (Exception ignorata) { }

        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setTypeface(font(c));
        p.setTextAlign(Paint.Align.CENTER);
        String vis = visibili(spenti);
        float x0 = PX * W, gw = W - 2 * x0, cw = gw / 7f;

        // testata: ‹ Mese Anno ›
        float hTop = PT * H, hH = TESTA * H;
        SimpleDateFormat fm = new SimpleDateFormat("LLLL yyyy", Locale.getDefault());
        Calendar k1 = Calendar.getInstance();
        k1.clear();
        k1.set(anno, mese, 1);
        String titolo = fm.format(k1.getTime());
        if (!titolo.isEmpty()) titolo = titolo.substring(0, 1).toUpperCase(Locale.getDefault()) + titolo.substring(1);
        float ts = Math.min(hH * 0.5f, W * 0.062f);
        p.setTextSize(ts);
        while (p.measureText(titolo) > W * 0.54f && ts > 8) { ts -= 1; p.setTextSize(ts); }
        p.setColor(t.testo);
        k.drawText(titolo, W / 2f, hTop + hH / 2f - (p.descent() + p.ascent()) / 2f, p);
        p.setColor(t.box);
        p.setTextSize(Math.min(hH * 0.78f, W * 0.09f));
        float ya = hTop + hH / 2f - (p.descent() + p.ascent()) / 2f;
        k.drawText("‹", x0 + W * 0.06f, ya, p);
        k.drawText("›", W - x0 - W * 0.06f, ya, p);

        // giorni della settimana (iniziali nella lingua del telefono)
        float sTop = hTop + hH, sH = SETT * H;
        SimpleDateFormat fw = new SimpleDateFormat("EEEEE", Locale.getDefault());
        Calendar kw = Calendar.getInstance();
        kw.clear();
        kw.set(2024, Calendar.JANUARY, lunedi ? 1 : 7);   // 1 gennaio 2024 = lunedi', 7 = domenica
        p.setColor(t.tenue);
        p.setTextSize(Math.min(sH * 0.62f, cw * 0.38f));
        for (int i = 0; i < 7; i++) {
            k.drawText(fw.format(kw.getTime()).toUpperCase(Locale.getDefault()), x0 + cw * i + cw / 2f, sTop + sH / 2f - (p.descent() + p.ascent()) / 2f, p);
            kw.add(Calendar.DAY_OF_MONTH, 1);
        }

        // griglia
        int off = vuote(anno, mese, lunedi), dim = giorniMese(anno, mese), righe = (off + dim + 6) / 7;
        float gTop = sTop + sH, gH = H * (1 - PT - TESTA - SETT - PB - (legenda ? LEG : 0)), rh = gH / righe;
        float fs = Math.min(rh * 0.34f, cw * 0.36f);
        Paint pt = new Paint(Paint.ANTI_ALIAS_FLAG);
        for (int i = 0; i < righe * 7; i++) {
            int g = i - off + 1;
            if (g < 1 || g > dim) continue;
            float cx = x0 + cw * (i % 7) + cw / 2f, cy0 = gTop + rh * (i / 7);
            String data = iso(anno, mese, g);
            boolean eOggi = data.equals(oggi), passato = data.compareTo(oggi) < 0;
            RectF box = new RectF(cx - cw / 2f + cw * 0.07f, cy0 + rh * 0.06f, cx + cw / 2f - cw * 0.07f, cy0 + rh * 0.94f);
            float rr = Math.min(cw, rh) * 0.2f;
            if (eOggi) {   // oggi: riquadro giallo
                pt.setStyle(Paint.Style.FILL);
                pt.setColor((t.box & 0x00FFFFFF) | 0x2E000000);
                k.drawRoundRect(box, rr, rr, pt);
                pt.setStyle(Paint.Style.STROKE);
                pt.setStrokeWidth(Math.max(2f, sc * 1.6f));
                pt.setColor(t.box);
                k.drawRoundRect(box, rr, rr, pt);
            }
            p.setTextSize(fs);
            p.setColor(passato ? ((t.testo & 0x00FFFFFF) | 0x73000000) : t.testo);
            k.drawText(String.valueOf(g), cx, cy0 + rh * 0.42f - (p.descent() + p.ascent()) / 2f, p);
            // pallini dei tornei di quel giorno
            String tipi = cal == null ? "" : cal.optString(data, "");
            StringBuilder q = new StringBuilder();
            for (char x : vis.toCharArray()) if (tipi.indexOf(x) >= 0) q.append(x);
            int n = q.length();
            if (n > 0) {
                float gap = Math.min(cw * 0.8f / n, rh * 0.17f), r = Math.min(gap * 0.36f, rh * 0.065f), cy = cy0 + rh * 0.76f;
                for (int j = 0; j < n; j++) {
                    int ci = ORDINE.indexOf(q.charAt(j));
                    float px = cx - (n - 1) * gap / 2f + j * gap;
                    pallino(k, pt, px, cy, r, ci, t, passato);
                }
            }
            if (eOggi && live) {   // LIVE sul bordo alto della casella di oggi
                float bh = Math.max(rh * 0.24f, 9 * sc * 0.9f), bw = bh * 2.6f, by = box.top - bh * 0.55f;
                RectF pill = new RectF(cx - bw / 2f, by, cx + bw / 2f, by + bh);
                pt.setStyle(Paint.Style.FILL);
                pt.setColor(Disegno.ROSSO);
                k.drawRoundRect(pill, bh / 2f, bh / 2f, pt);
                pt.setColor(Color.WHITE);
                k.drawCircle(pill.left + bh * 0.45f, pill.centerY(), bh * 0.15f, pt);
                Paint pl = new Paint(p);
                pl.setColor(Color.WHITE);
                pl.setTextSize(bh * 0.66f);
                k.drawText("LIVE", pill.centerX() + bh * 0.22f, pill.centerY() - (pl.descent() + pl.ascent()) / 2f, pl);
            }
        }

        // legenda: solo i tipi visibili, 4 per riga
        if (legenda) {
            float lTop = gTop + gH, lH = LEG * H;
            int n = vis.length(), per = 4, rr2 = (n + per - 1) / per;
            float colw = gw / per, rowH = lH / Math.max(rr2, 2), y00 = lTop + (lH - rowH * rr2) / 2f;
            Paint pl = new Paint(Paint.ANTI_ALIAS_FLAG);
            pl.setTypeface(font(c));
            pl.setColor(t.tenue);
            float lfs = Math.min(rowH * 0.56f, colw * 0.16f);
            for (int i = 0; i < n; i++) {
                int ci = ORDINE.indexOf(vis.charAt(i));
                float lx = x0 + colw * (i % per) + colw * 0.04f, cy = y00 + rowH * (i / per) + rowH / 2f, r = lfs * 0.36f;
                pallino(k, pt, lx + r, cy, r, ci, t, false);
                String s = c.getString(NOMI[ci]);
                float fsz = lfs;
                pl.setTextSize(fsz);
                float max = colw - r * 2 - lfs * 0.5f - colw * 0.06f;
                while (pl.measureText(s) > max && fsz > 6) { fsz -= 0.5f; pl.setTextSize(fsz); }
                k.drawText(s, lx + r * 2 + lfs * 0.4f, cy - (pl.descent() + pl.ascent()) / 2f, pl);
            }
        }
        return b;
    }

    private static void pallino(Canvas k, Paint pt, float x, float y, float r, int ci, Tema t, boolean tenue) {
        pt.setStyle(Paint.Style.FILL);
        int col = COLORI[ci];
        if (tenue) col = (col & 0x00FFFFFF) | 0x8C000000;
        pt.setColor(col);
        k.drawCircle(x, y, r, pt);
        if (ci == 3 || ci == 7) {   // bianco e nero: bordino perche' si vedano su ogni sfondo
            pt.setStyle(Paint.Style.STROKE);
            pt.setStrokeWidth(Math.max(1f, r * 0.28f));
            pt.setColor(t.tenue);
            k.drawCircle(x, y, r, pt);
        }
    }
}
