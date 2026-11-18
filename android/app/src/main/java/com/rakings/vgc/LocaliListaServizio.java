package com.rakings.vgc;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.widget.RemoteViews;
import android.widget.RemoteViewsService;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/** Elenco del widget Top 8 dei locali: per ogni torneo una riga di titolo e le 8 righe dei giocatori (con la squadra scritta, se c'e'). */
public class LocaliListaServizio extends RemoteViewsService {
    @Override
    public RemoteViewsFactory onGetViewFactory(Intent i) {
        return new Fabbrica(getApplicationContext(), i.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, 0));
    }

    static final class Fabbrica implements RemoteViewsFactory {
        final Context c; final int id;
        /** ogni elemento: {tipo, url, ...}  tipo 0 = titolo del torneo [0,url,titolo,info]; tipo 1 = giocatore [1,url,pos,nome,squadra] */
        final List<String[]> righe = new ArrayList<>();
        Fabbrica(Context c, int id) { this.c = c; this.id = id; }
        @Override public void onCreate() { }
        @Override public void onDataSetChanged() {
            righe.clear();
            JSONArray a = Dati.w(c).optJSONArray("lc");
            int k = a == null ? 0 : Math.min(WidgetLocali.quanti(c, id), a.length());
            for (int i = 0; i < k; i++) {
                JSONObject l = a.optJSONObject(i);
                if (l == null) continue;
                String u = l.optString("u", Dati.SITO);
                StringBuilder info = new StringBuilder();
                for (String s : new String[]{l.optString("s"), l.optString("c"), l.optString("d")}) {
                    if (s.isEmpty()) continue;
                    if (info.length() > 0) info.append(" · ");
                    info.append(s);
                }
                if (l.optInt("n") > 0) info.append(info.length() > 0 ? " · " : "").append(c.getString(R.string.n_giocatori, l.optInt("n")));
                righe.add(new String[]{"0", u, l.optString("t"), info.toString()});
                JSONArray top = l.optJSONArray("top");
                JSONObject tm = l.optJSONObject("tm");
                for (int p = 0; top != null && p < top.length() && p < 8; p++) {
                    JSONArray sq = tm == null ? null : tm.optJSONArray(String.valueOf(p));
                    StringBuilder q = new StringBuilder();
                    for (int j = 0; sq != null && j < sq.length(); j++) { if (j > 0) q.append(" · "); q.append(sq.optString(j)); }
                    righe.add(new String[]{"1", u, String.valueOf(p + 1), top.optString(p), q.toString()});
                }
            }
        }
        @Override public void onDestroy() { righe.clear(); }
        @Override public int getCount() { return righe.size(); }
        @Override public RemoteViews getViewAt(int i) {
            if (i < 0 || i >= righe.size()) return null;
            String[] x = righe.get(i);
            Tema t = Tema.attuale(c);
            RemoteViews v;
            if ("0".equals(x[0])) {
                v = new RemoteViews(c.getPackageName(), R.layout.w_lc_testa);
                v.setTextViewText(R.id.h_tit, x[2]);
                v.setTextColor(R.id.h_tit, t.box);
                v.setTextViewText(R.id.h_info, x[3]);
                v.setTextColor(R.id.h_info, t.tenue);
            } else {
                v = new RemoteViews(c.getPackageName(), R.layout.w_lc_riga);
                int pos = Integer.parseInt(x[2]);
                v.setTextViewText(R.id.r_pos, x[2]);
                v.setTextColor(R.id.r_pos, pos == 1 ? t.box : pos == 2 ? (t.chiaro ? 0xFF6B7280 : 0xFFC9D1DB) : pos == 3 ? (t.chiaro ? 0xFFA0522D : 0xFFE0A16A) : t.tenue);
                v.setTextViewText(R.id.r_nome, x[3]);
                v.setTextColor(R.id.r_nome, t.testo);
                v.setTextViewText(R.id.r_team, x[4]);
                v.setTextColor(R.id.r_team, t.tenue);
                v.setViewVisibility(R.id.r_team, x[4].isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);
            }
            v.setOnClickFillInIntent(R.id.riga, new Intent().setData(Uri.parse(x[1])));
            return v;
        }
        @Override public RemoteViews getLoadingView() { return null; }
        @Override public int getViewTypeCount() { return 2; }
        @Override public long getItemId(int i) { return i; }
        @Override public boolean hasStableIds() { return false; }
    }
}
