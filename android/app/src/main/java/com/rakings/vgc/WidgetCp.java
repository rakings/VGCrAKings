package com.rakings.vgc;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

/** Widget CP BAR: in alto il giocatore scelto nelle impostazioni (o la soglia se non c'e'), sotto la Top 10/25/50 che scorre. */
public class WidgetCp extends Base {

    static SharedPreferences imp(Context c) { return c.getSharedPreferences("cp_widget", Context.MODE_PRIVATE); }

    /** se un widget segue un giocatore oltre i primi 150, aggiorna (al massimo una volta al giorno) la classifica completa */
    static void preparaGiocatori(Context c) {
        for (Object o : imp(c).getAll().entrySet().toArray()) {
            java.util.Map.Entry<?, ?> e = (java.util.Map.Entry<?, ?>) o;
            if (!String.valueOf(e.getKey()).startsWith("nome_")) continue;
            String n = String.valueOf(e.getValue());
            if (!n.isEmpty()) { Dati.giocatore(c, n, true); }
        }
    }

    @Override
    public void onDeleted(Context c, int[] ids) {
        SharedPreferences.Editor e = imp(c).edit();
        for (int id : ids) e.remove("nome_" + id).remove("top_" + id);
        e.apply();
    }

    @Override
    void disegna(Context c, AppWidgetManager m, int id) {
        JSONObject cp = Dati.w(c).optJSONObject("cp");
        if (cp == null) cp = new JSONObject();
        String nome = imp(c).getString("nome_" + id, "");
        int top = imp(c).getInt("top_" + id, 10);
        int[] mis = misura(m, id);
        boolean piccolo = mis[0] < 220;
        int sg = cp.optInt("sg", 0);
        JSONArray g = Dati.giocatore(c, nome, false);
        String urlCp = Dati.SITO + "#cpbar";
        RemoteViews v = new RemoteViews(c.getPackageName(), piccolo ? R.layout.w_cp_piccolo : R.layout.w_cp_grande);
        Tema t = Tema.attuale(c);
        tema(v, t, true);
        v.setInt(R.id.box, "setBackgroundResource", t.riquadro);
        v.setTextColor(R.id.b_nome, t.testo);
        v.setTextColor(R.id.b_info, t.tenue);
        v.setTextColor(R.id.b_cp, t.box);
        if (piccolo) v.setTextColor(R.id.b_pos, t.testo);
        else { v.setTextColor(R.id.s_top, t.box); v.setTextColor(R.id.s_soglia, t.tenue); }
        v.setTextViewText(R.id.t_titolo, c.getString(R.string.w_cp));
        v.setTextViewText(R.id.t_destra, piccolo ? "" : c.getString(R.string.europa) + " · VG Masters");
        if (g != null) {
            int pos = g.optInt(0), punti = g.optInt(3), d = punti - sg;
            v.setTextViewText(R.id.b_nome, "★ " + g.optString(1));
            v.setTextViewText(R.id.b_cp, piccolo ? punti + " CP" : String.valueOf(punti));
            if (piccolo) {
                v.setTextViewText(R.id.b_info, g.optString(2));
                v.setTextViewText(R.id.b_pos, Testo.posto(c, pos));
            } else v.setTextViewText(R.id.b_info, Testo.posto(c, pos) + " · " + g.optString(2));
            v.setTextViewText(R.id.b_delta, sg <= 0 ? "" : d >= 0 ? c.getString(R.string.sopra, d) : c.getString(R.string.sotto, -d));
            v.setTextColor(R.id.b_delta, d >= 0 ? (t.chiaro ? Color.parseColor("#15803D") : Color.parseColor("#4ADE80")) : (t.chiaro ? Color.parseColor("#B91C1C") : Color.parseColor("#FF6B78")));
        } else {
            // nessun giocatore scelto (o non trovato): la soglia
            v.setTextViewText(R.id.b_nome, c.getString(R.string.soglia_stimata));
            v.setTextViewText(R.id.b_cp, sg > 0 ? sg + (piccolo ? " CP" : "") : "—");
            String sp = cp.optInt("sp", 0) > 0 ? Testo.posto(c, cp.optInt("sp")) : "";
            if (piccolo) { v.setTextViewText(R.id.b_info, ""); v.setTextViewText(R.id.b_pos, sp); }
            else v.setTextViewText(R.id.b_info, sp);
            v.setTextViewText(R.id.b_delta, nome.isEmpty() ? c.getString(R.string.nessun_giocatore) : "");
            v.setTextColor(R.id.b_delta, t.tenue);
        }
        if (!piccolo) {
            boolean lista = top > 0;
            v.setViewVisibility(R.id.sub, lista ? android.view.View.VISIBLE : android.view.View.GONE);
            v.setViewVisibility(R.id.lista, lista ? android.view.View.VISIBLE : android.view.View.GONE);
            v.setTextViewText(R.id.s_top, c.getString(R.string.top_n, top));
            v.setTextViewText(R.id.s_soglia, sg > 0 ? c.getString(R.string.soglia_cp, sg) : "");
            if (lista) {
                Intent s = new Intent(c, CpListaServizio.class);
                s.putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
                s.setData(Uri.parse("rakings://cp/" + id + "/" + top + "/" + Uri.encode(nome) + "/" + Dati.pref(c).getLong("quando", 0)));
                v.setRemoteAdapter(R.id.lista, s);
                v.setPendingIntentTemplate(R.id.lista, apri(c, urlCp, id * 10 + 2));
                m.notifyAppWidgetViewDataChanged(id, R.id.lista);
            }
        }
        v.setOnClickPendingIntent(R.id.radice, apri(c, urlCp, id * 10 + 1));
        m.updateAppWidget(id, v);
    }
}
