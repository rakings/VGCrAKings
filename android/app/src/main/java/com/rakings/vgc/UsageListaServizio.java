package com.rakings.vgc;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;
import android.widget.RemoteViewsService;

import org.json.JSONArray;
import org.json.JSONObject;

/** Elenco del widget Top usage: per ogni Pokemon posizione, nome, % di squadre, poi strumenti/abilita'/natura e le mosse. */
public class UsageListaServizio extends RemoteViewsService {
    @Override
    public RemoteViewsFactory onGetViewFactory(Intent i) {
        return new Fabbrica(getApplicationContext(), i.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, 0));
    }

    static final class Fabbrica implements RemoteViewsFactory {
        final Context c; final int id; JSONArray r = new JSONArray(); int n = 0;
        Fabbrica(Context c, int id) { this.c = c; this.id = id; }
        @Override public void onCreate() { }
        @Override public void onDataSetChanged() {
            JSONObject u = Dati.usage(c, false);
            r = u == null || u.optJSONArray("r") == null ? new JSONArray() : u.optJSONArray("r");
            n = Math.min(WidgetUsage.quanti(c, id), r.length());
        }
        @Override public void onDestroy() { }
        @Override public int getCount() { return n; }

        /** [["Miracle Seed",74],["Life Orb",8]] -> "Miracle Seed 74% · Life Orb 8%" (al massimo k voci) */
        static String voci(JSONArray a, int k, boolean perc) {
            StringBuilder s = new StringBuilder();
            for (int i = 0; a != null && i < a.length() && i < k; i++) {
                JSONArray x = a.optJSONArray(i);
                if (x == null) continue;
                if (s.length() > 0) s.append(" · ");
                s.append(x.optString(0));
                if (perc) s.append(' ').append(x.optInt(1)).append('%');
            }
            return s.toString();
        }

        @Override public RemoteViews getViewAt(int i) {
            RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.w_us_riga);
            JSONArray x = r.optJSONArray(i);
            if (x == null) return v;
            Tema t = Tema.attuale(c);
            v.setTextViewText(R.id.r_pos, String.valueOf(i + 1));
            v.setTextColor(R.id.r_pos, i == 0 ? t.box : i == 1 ? (t.chiaro ? 0xFF6B7280 : 0xFFC9D1DB) : i == 2 ? (t.chiaro ? 0xFFA0522D : 0xFFE0A16A) : t.tenue);
            v.setTextViewText(R.id.r_nome, x.optString(0));
            v.setTextColor(R.id.r_nome, t.testo);
            double p = x.optDouble(1);
            v.setTextViewText(R.id.r_uso, (p == Math.floor(p) ? String.valueOf((int) p) : String.valueOf(p)) + "%");
            v.setTextColor(R.id.r_uso, t.box);
            String set = voci(x.optJSONArray(2), 2, true);
            String ab = voci(x.optJSONArray(3), 1, true), nt = voci(x.optJSONArray(4), 1, true);
            if (!ab.isEmpty()) set += (set.isEmpty() ? "" : " · ") + ab;
            if (!nt.isEmpty()) set += (set.isEmpty() ? "" : " · ") + nt;
            v.setTextViewText(R.id.r_set, set);
            v.setTextColor(R.id.r_set, t.tenue);
            v.setViewVisibility(R.id.r_set, set.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);
            String mo = voci(x.optJSONArray(5), 4, false);
            v.setTextViewText(R.id.r_mosse, mo);
            v.setTextColor(R.id.r_mosse, t.tenue);
            v.setViewVisibility(R.id.r_mosse, mo.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);
            v.setOnClickFillInIntent(R.id.riga, new Intent());
            return v;
        }
        @Override public RemoteViews getLoadingView() { return null; }
        @Override public int getViewTypeCount() { return 1; }
        @Override public long getItemId(int i) { return i; }
        @Override public boolean hasStableIds() { return true; }
    }
}
