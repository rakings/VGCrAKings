package com.rakings.vgc;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;
import android.widget.RemoteViewsService;

import org.json.JSONArray;
import org.json.JSONObject;

/** Elenco che scorre dentro il widget CP bar (Top 10/25/50). Il giocatore scelto e' evidenziato. */
public class CpListaServizio extends RemoteViewsService {
    @Override
    public RemoteViewsFactory onGetViewFactory(Intent i) {
        return new Fabbrica(getApplicationContext(), i.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, 0));
    }

    static final class Fabbrica implements RemoteViewsFactory {
        final Context c; final int id; JSONArray r = new JSONArray(); int n = 0; String nome = "";
        Fabbrica(Context c, int id) { this.c = c; this.id = id; }
        @Override public void onCreate() { }
        @Override public void onDataSetChanged() {
            JSONObject cp = Dati.w(c).optJSONObject("cp");
            r = cp == null || cp.optJSONArray("r") == null ? new JSONArray() : cp.optJSONArray("r");
            n = Math.min(WidgetCp.imp(c).getInt("top_" + id, 10), r.length());
            nome = WidgetCp.imp(c).getString("nome_" + id, "");
        }
        @Override public void onDestroy() { }
        @Override public int getCount() { return n; }
        @Override public RemoteViews getViewAt(int i) {
            RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.w_cp_riga);
            JSONArray x = r.optJSONArray(i);
            if (x == null) return v;
            Tema t = Tema.attuale(c);
            v.setTextViewText(R.id.r_pos, String.valueOf(x.optInt(0)));
            v.setTextColor(R.id.r_pos, t.tenue);
            v.setTextColor(R.id.r_nome, t.testo);
            v.setTextColor(R.id.r_cp, t.testo);
            String paese = x.optString(2);
            v.setTextViewText(R.id.r_nome, android.text.Html.fromHtml(android.text.TextUtils.htmlEncode(x.optString(1)) + " <small><font color='" + String.format("#%06X", t.tenue & 0xFFFFFF) + "'>" + paese + "</font></small>"));
            v.setTextViewText(R.id.r_cp, String.valueOf(x.optInt(3)));
            v.setInt(R.id.riga, "setBackgroundResource", nome.equals(x.optString(1)) ? (t.chiaro ? R.drawable.fondo_riga_mia_chiaro : R.drawable.fondo_riga_mia) : 0);
            v.setOnClickFillInIntent(R.id.riga, new Intent());
            return v;
        }
        @Override public RemoteViews getLoadingView() { return null; }
        @Override public int getViewTypeCount() { return 1; }
        @Override public long getItemId(int i) { return i; }
        @Override public boolean hasStableIds() { return true; }
    }
}
