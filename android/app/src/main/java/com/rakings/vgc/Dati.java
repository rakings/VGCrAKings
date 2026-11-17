package com.rakings.vgc;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/** Dati dei widget: un solo file piccolo (widget.json) per tutti e tre, salvato sul telefono.
 *  Lo stato LIVE si legge solo nei giorni del torneo. La classifica completa CP solo se serve (giocatore oltre i primi 150), una volta al giorno. */
final class Dati {
    static final String SITO = "https://rakings.github.io/VGCrAKings/";
    static final String URL_W = SITO + "widget.json";
    private static final long OGNI = 10 * 60 * 1000L;          // non riscaricare prima di 10 minuti
    private static final long TUTTI_OGNI = 20 * 60 * 60 * 1000L; // classifica completa: al massimo una volta ogni 20 ore

    static SharedPreferences pref(Context c) { return c.getSharedPreferences("dati", Context.MODE_PRIVATE); }

    static JSONObject w(Context c) {
        try { return new JSONObject(pref(c).getString("w", "{}")); } catch (Exception e) { return new JSONObject(); }
    }

    static String scarica(String u) throws Exception {
        HttpURLConnection h = (HttpURLConnection) new URL(u + (u.contains("?") ? "&" : "?") + "t=" + (System.currentTimeMillis() / 60000)).openConnection();
        h.setConnectTimeout(12000);
        h.setReadTimeout(15000);
        h.setRequestProperty("Cache-Control", "no-cache");
        try (InputStream in = h.getInputStream()) {
            ByteArrayOutputStream o = new ByteArrayOutputStream();
            byte[] b = new byte[16384];
            int n;
            while ((n = in.read(b)) > 0) o.write(b, 0, n);
            return new String(o.toByteArray(), StandardCharsets.UTF_8);
        } finally { h.disconnect(); }
    }

    static String oggi() {
        SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd", Locale.US);
        f.setTimeZone(TimeZone.getTimeZone("Europe/Rome"));
        return f.format(new Date());
    }

    static boolean inCorso(JSONObject e) {
        if (e == null) return false;
        String t = oggi();
        return e.optString("d").compareTo(t) <= 0 && e.optString("e", e.optString("d")).compareTo(t) >= 0;
    }

    /** Aggiorna i dati (se non sono freschi). Ritorna true se qualcosa e' cambiato. */
    static boolean aggiorna(Context c, boolean forza) {
        SharedPreferences p = pref(c);
        long ora = System.currentTimeMillis();
        if (!forza && ora - p.getLong("quando", 0) < OGNI) return false;
        boolean cambiato = false;
        SharedPreferences.Editor ed = p.edit();
        try {
            String s = scarica(URL_W);
            JSONObject w = new JSONObject(s);
            if (!s.equals(p.getString("w", ""))) { ed.putString("w", s); cambiato = true; }
            ed.putLong("quando", ora);
            // LIVE: solo se oggi c'e' il torneo
            String lr = "", lv = "";
            JSONObject rg = w.optJSONObject("rg"), vr = w.optJSONObject("vr");
            JSONObject live = w.optJSONObject("live");
            if (live != null && inCorso(rg)) lr = cercaLive(live.optString("reg"), rg, false);
            if (live != null && inCorso(vr)) lv = cercaLive(live.optString("vr"), vr, true);
            if (!lr.equals(p.getString("live_rg", "")) || !lv.equals(p.getString("live_vr", ""))) cambiato = true;
            ed.putString("live_rg", lr).putString("live_vr", lv);
        } catch (Exception ignorata) {
            // niente rete: restano gli ultimi dati buoni
        }
        ed.apply();
        return cambiato;
    }

    private static String cercaLive(String url, JSONObject e, boolean vr) {
        if (url == null || url.isEmpty()) return "";
        try {
            JSONArray a = new JSONObject(scarica(url)).optJSONArray("events");
            if (a == null) return "";
            String d = e.optString("d"), f = e.optString("e", d), nome = norma(e.optString("n"));
            for (int i = 0; i < a.length(); i++) {
                JSONObject x = a.getJSONObject(i);
                if (!"running".equals(x.optString("status"))) continue;
                String xs = x.optString("start"), xe = x.optString("end", xs);
                boolean ok = vr ? (xs.equals(d) || norma(x.optString("name")).endsWith(nome)) : (xs.compareTo(f) <= 0 && xe.compareTo(d) >= 0);
                if (ok) return x.optString("id");
            }
        } catch (Exception ignorata) { }
        return "";
    }

    static String norma(String s) { return s == null ? "" : s.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", ""); }

    /** Classifica completa CP (per cercare/mostrare un giocatore oltre i primi 150). */
    static JSONArray tutti(Context c, boolean scaricaSeServe) {
        File f = new File(c.getFilesDir(), "cp_tutti.json");
        SharedPreferences p = pref(c);
        if (scaricaSeServe && (!f.exists() || System.currentTimeMillis() - p.getLong("tutti_quando", 0) > TUTTI_OGNI)) {
            try {
                JSONObject cp = w(c).optJSONObject("cp");
                String u = cp == null ? "" : cp.optString("tutti");
                if (!u.isEmpty()) {
                    String s = scarica(u);
                    new JSONObject(s); // controllo che sia valido
                    try (FileOutputStream o = new FileOutputStream(f)) { o.write(s.getBytes(StandardCharsets.UTF_8)); }
                    p.edit().putLong("tutti_quando", System.currentTimeMillis()).apply();
                }
            } catch (Exception ignorata) { }
        }
        try {
            if (!f.exists()) return null;
            byte[] b = new byte[(int) f.length()];
            try (InputStream in = new java.io.FileInputStream(f)) { int l = 0; while (l < b.length) { int n = in.read(b, l, b.length - l); if (n < 0) break; l += n; } }
            return new JSONObject(new String(b, StandardCharsets.UTF_8)).optJSONArray("r");
        } catch (Exception e) { return null; }
    }

    /** Riga CP di un giocatore per nome: [pos, nome, paese, cp], prima tra i primi 150, poi nella classifica completa. */
    static JSONArray giocatore(Context c, String nome, boolean scaricaSeServe) {
        if (nome == null || nome.isEmpty()) return null;
        JSONObject cp = w(c).optJSONObject("cp");
        JSONArray r = cp == null ? null : cp.optJSONArray("r");
        JSONArray x = trova(r, nome);
        if (x != null) return x;
        JSONArray t = tutti(c, scaricaSeServe);
        if (t == null) return null;
        // classifica completa: [pos, rank, nome, paese, cp] -> [pos, nome, paese, cp]
        for (int i = 0; i < t.length(); i++) {
            JSONArray y = t.optJSONArray(i);
            if (y != null && nome.equals(y.optString(2))) {
                JSONArray z = new JSONArray();
                z.put(y.optInt(0)); z.put(y.optString(2)); z.put(y.optString(3)); z.put(y.optInt(4));
                return z;
            }
        }
        return null;
    }

    private static JSONArray trova(JSONArray r, String nome) {
        if (r == null) return null;
        for (int i = 0; i < r.length(); i++) {
            JSONArray y = r.optJSONArray(i);
            if (y != null && nome.equals(y.optString(1))) return y;
        }
        return null;
    }
}
