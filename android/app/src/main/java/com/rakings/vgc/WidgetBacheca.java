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

/** Widget BACHECA: un annuncio alla volta (prima quello «In evidenza», poi i piu' recenti), con «›» per passare al successivo. */
public class WidgetBacheca extends Base {
    static final String AVANTI = "com.rakings.vgc.BK_AVANTI";

    @Override
    public void onReceive(Context c, Intent i) {
        if (AVANTI.equals(i.getAction())) {
            int id = i.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, 0);
            android.content.SharedPreferences p = c.getSharedPreferences("bk_widget", Context.MODE_PRIVATE);
            p.edit().putInt("i_" + id, p.getInt("i_" + id, 0) + 1).apply();
            disegna(c, AppWidgetManager.getInstance(c), id);
            return;
        }
        super.onReceive(c, i);
    }

    @Override
    void disegna(Context c, AppWidgetManager m, int id) {
        JSONArray a = Dati.w(c).optJSONArray("bk");
        int[] mis = misura(m, id);
        boolean largo = mis[0] >= 220;
        RemoteViews v = new RemoteViews(c.getPackageName(), largo ? R.layout.w_bk_largo : R.layout.w_bk_piccolo);
        Tema t = Tema.attuale(c);
        tema(v, t, largo);
        v.setTextColor(R.id.tit, t.testo);
        if (largo) { v.setTextColor(R.id.txt, t.tenue); v.setTextColor(R.id.avanti, t.accento); }
        if (largo) {
            v.setTextViewText(R.id.t_titolo, c.getString(R.string.w_bk));
            v.setTextViewText(R.id.t_destra, a == null || a.length() < 2 ? "" : ((c.getSharedPreferences("bk_widget", Context.MODE_PRIVATE).getInt("i_" + id, 0) % a.length()) + 1) + "/" + a.length());
        }
        if (a == null || a.length() == 0) {
            v.setTextViewText(R.id.tit, c.getString(R.string.nessun_annuncio));
            v.setTextViewText(R.id.tag, "");
            m.updateAppWidget(id, v);
            return;
        }
        int i = c.getSharedPreferences("bk_widget", Context.MODE_PRIVATE).getInt("i_" + id, 0) % a.length();
        JSONObject x = a.optJSONObject(i);
        boolean pin = x.optBoolean("pin");
        String tag = pin ? c.getString(R.string.in_evidenza) : x.optString("p");
        v.setTextViewText(R.id.tag, tag);
        v.setViewVisibility(R.id.tag, tag.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);
        v.setInt(R.id.tag, "setBackgroundResource", pin ? R.drawable.fondo_tag_pin : R.drawable.fondo_tag);
        v.setTextColor(R.id.tag, pin ? 0xFF3A2A00 : 0xFFFFFFFF);
        v.setTextViewText(R.id.tit, x.optString("t"));
        if (largo) {
            v.setTextViewText(R.id.txt, x.optString("d"));
            Intent av = new Intent(c, WidgetBacheca.class).setAction(AVANTI).putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
            v.setOnClickPendingIntent(R.id.avanti, PendingIntent.getBroadcast(c, id, av, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));
            v.setViewVisibility(R.id.avanti, a.length() > 1 ? android.view.View.VISIBLE : android.view.View.GONE);
        }
        Bitmap img = immagine(c, x);
        if (img != null) { v.setImageViewBitmap(R.id.img, img); v.setViewVisibility(R.id.img, android.view.View.VISIBLE); }
        else v.setImageViewResource(R.id.img, R.mipmap.ic_launcher);
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
