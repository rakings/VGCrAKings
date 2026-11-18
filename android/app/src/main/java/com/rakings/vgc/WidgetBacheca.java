package com.rakings.vgc;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** Widget BACHECA: gli ultimi 1, 2 o 3 annunci (si sceglie nelle impostazioni del widget; prima quello «In evidenza»).
 *  Ogni annuncio prende la stessa altezza: la riga diventa piu' grande o piu' piccola secondo lo spazio, cosi' il widget non resta vuoto. */
public class WidgetBacheca extends Base {
    static final String AVANTI = "com.rakings.vgc.BK_AVANTI";   // vecchio pulsante «›»: non si usa piu', resta per i widget gia' messi

    static android.content.SharedPreferences imp(Context c) { return c.getSharedPreferences("bk_widget", Context.MODE_PRIVATE); }
    static int quanti(Context c, int id) { return Math.max(1, Math.min(3, imp(c).getInt("n_" + id, 2))); }

    @Override
    public void onReceive(Context c, Intent i) {
        if (AVANTI.equals(i.getAction())) { disegna(c, AppWidgetManager.getInstance(c), i.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, 0)); return; }
        super.onReceive(c, i);
    }

    @Override
    public void onDeleted(Context c, int[] ids) {
        android.content.SharedPreferences.Editor e = imp(c).edit();
        for (int id : ids) e.remove("n_" + id).remove("i_" + id);
        e.apply();
    }

    @Override
    void disegna(Context c, AppWidgetManager m, int id) {
        JSONArray a = Dati.w(c).optJSONArray("bk");
        int[] mis = misura(m, id);
        Tema t = Tema.attuale(c);
        if (mis[0] < 220) { piccolo(c, m, id, a, t); return; }
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.w_bk_lista);
        tema(v, t, true);
        v.setTextViewText(R.id.t_titolo, c.getString(R.string.w_bk));
        v.setTextViewText(R.id.t_destra, "");
        v.removeAllViews(R.id.lista);
        int k = a == null ? 0 : Math.min(quanti(c, id), a.length());
        if (k == 0) {
            v.setViewVisibility(R.id.lista, android.view.View.GONE);
            v.setViewVisibility(R.id.vuoto, android.view.View.VISIBLE);
            v.setTextViewText(R.id.vuoto, c.getString(R.string.nessun_annuncio));
            v.setTextColor(R.id.vuoto, t.tenue);
            v.setOnClickPendingIntent(R.id.radice, apri(c, Dati.SITO, id * 10 + 1));
            m.updateAppWidget(id, v);
            return;
        }
        // altezza di ogni riga (dp): testata ~34dp, margine in basso 8dp
        int hr = (mis[1] - 42) / k;
        int lay = hr >= 132 ? R.layout.w_bk_r_grande : hr >= 84 ? R.layout.w_bk_r_media : R.layout.w_bk_r_piccola;
        for (int i = 0; i < k; i++) {
            JSONObject x = a.optJSONObject(i);
            if (x == null) continue;
            RemoteViews r = new RemoteViews(c.getPackageName(), lay);
            riempi(c, r, x, t);
            r.setOnClickPendingIntent(R.id.riga, apri(c, x.optString("u"), id * 10 + 2 + i));
            v.addView(R.id.lista, r);
        }
        v.setOnClickPendingIntent(R.id.radice, apri(c, Dati.SITO, id * 10 + 1));
        m.updateAppWidget(id, v);
    }

    /** una riga: etichetta, titolo, testo, immagine (o l'uovo se l'annuncio non ha foto) */
    static void riempi(Context c, RemoteViews r, JSONObject x, Tema t) {
        boolean pin = x.optBoolean("pin");
        String tag = pin ? c.getString(R.string.in_evidenza) : x.optString("p");
        r.setTextViewText(R.id.tag, tag);
        r.setViewVisibility(R.id.tag, tag.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);
        r.setInt(R.id.tag, "setBackgroundResource", pin ? R.drawable.fondo_tag_pin : R.drawable.fondo_tag);
        r.setTextColor(R.id.tag, pin ? 0xFF3A2A00 : 0xFFFFFFFF);
        r.setTextViewText(R.id.tit, x.optString("t"));
        r.setTextColor(R.id.tit, t.testo);
        String d = x.optString("d").replace('\n', ' ').trim();
        r.setTextViewText(R.id.txt, d);
        r.setTextColor(R.id.txt, t.tenue);
        r.setViewVisibility(R.id.txt, d.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);
        Bitmap img = immagine(c, x);
        if (img != null) r.setImageViewBitmap(R.id.img, img); else r.setImageViewResource(R.id.img, R.mipmap.ic_launcher);
    }

    /** formato stretto (1 casella di larghezza): un solo annuncio, immagine sopra e titolo sotto */
    void piccolo(Context c, AppWidgetManager m, int id, JSONArray a, Tema t) {
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.w_bk_piccolo);
        tema(v, t, false);
        v.setTextColor(R.id.tit, t.testo);
        JSONObject x = a == null ? null : a.optJSONObject(0);
        if (x == null) {
            v.setTextViewText(R.id.tit, c.getString(R.string.nessun_annuncio));
            v.setTextViewText(R.id.tag, "");
            v.setViewVisibility(R.id.tag, android.view.View.GONE);
            v.setImageViewResource(R.id.img, R.mipmap.ic_launcher);
            v.setOnClickPendingIntent(R.id.radice, apri(c, Dati.SITO, id * 10 + 1));
            m.updateAppWidget(id, v);
            return;
        }
        boolean pin = x.optBoolean("pin");
        String tag = pin ? c.getString(R.string.in_evidenza) : x.optString("p");
        v.setTextViewText(R.id.tag, tag);
        v.setViewVisibility(R.id.tag, tag.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);
        v.setInt(R.id.tag, "setBackgroundResource", pin ? R.drawable.fondo_tag_pin : R.drawable.fondo_tag);
        v.setTextColor(R.id.tag, pin ? 0xFF3A2A00 : 0xFFFFFFFF);
        v.setTextViewText(R.id.tit, x.optString("t"));
        Bitmap img = immagine(c, x);
        if (img != null) v.setImageViewBitmap(R.id.img, img); else v.setImageViewResource(R.id.img, R.mipmap.ic_launcher);
        v.setOnClickPendingIntent(R.id.radice, apri(c, x.optString("u"), id * 10 + 1));
        m.updateAppWidget(id, v);
    }

    /** immagine dell'annuncio: salvata sul telefono, rimpicciolita (leggera) */
    static Bitmap immagine(Context c, JSONObject x) {
        String u = x.optString("img");
        if (u.isEmpty()) return null;
        File f = new File(c.getCacheDir(), "bk_" + x.optLong("id") + ".png");
        if (f.exists()) return BitmapFactory.decodeFile(f.getPath());
        return null;
    }

    /** scarica in anticipo le immagini degli annunci (chiamato dopo l'aggiornamento dei dati, fuori dal thread principale) */
    static void scaricaImmagini(Context c) {
        JSONArray a = Dati.w(c).optJSONArray("bk");
        if (a == null) return;
        for (int i = 0; i < a.length(); i++) {
            JSONObject x = a.optJSONObject(i);
            String u = x == null ? "" : x.optString("img");
            if (u.isEmpty()) continue;
            File f = new File(c.getCacheDir(), "bk_" + x.optLong("id") + ".png");
            if (f.exists()) continue;
            try {
                HttpURLConnection h = (HttpURLConnection) new URL(u).openConnection();
                h.setConnectTimeout(12000); h.setReadTimeout(15000);
                Bitmap b;
                try (InputStream in = h.getInputStream()) { b = BitmapFactory.decodeStream(in); } finally { h.disconnect(); }
                if (b == null) continue;
                int lato = 240, w = b.getWidth(), hh = b.getHeight(), s = Math.min(w, hh);
                Bitmap q = Bitmap.createBitmap(b, (w - s) / 2, (hh - s) / 2, s, s);
                Bitmap r = Bitmap.createScaledBitmap(q, lato, lato, true);
                try (FileOutputStream o = new FileOutputStream(f)) { r.compress(Bitmap.CompressFormat.PNG, 100, o); }
            } catch (Exception ignorata) { }
        }
    }
}
