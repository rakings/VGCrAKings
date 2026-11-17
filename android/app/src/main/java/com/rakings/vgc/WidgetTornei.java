package com.rakings.vgc;

import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

/** Widget TORNEI: quadrato diagonale (prossimo VR + prossimo Regionale/Internazionale, LIVE durante il torneo)
 *  e, nel formato largo, i prossimi 3 money tournament dal premio piu' alto. */
public class WidgetTornei extends Base {

    @Override
    void disegna(Context c, AppWidgetManager m, int id) {
        JSONObject w = Dati.w(c);
        SharedPreferences p = Dati.pref(c);
        JSONObject vr = w.optJSONObject("vr"), rg = w.optJSONObject("rg");
        String lv = p.getString("live_vr", ""), lr = p.getString("live_rg", "");
        int[] mis = misura(m, id);
        boolean largo = mis[0] >= 220;
        float dens = c.getResources().getDisplayMetrics().density;
        int lato = (int) (Math.min(largo ? mis[1] : Math.min(mis[0], mis[1]), 200) * dens);
        RemoteViews v = new RemoteViews(c.getPackageName(), largo ? R.layout.w_tornei_largo : R.layout.w_tornei_quadrato);
        v.setImageViewBitmap(R.id.quadrato, Disegno.quadrato(c, lato, vr, rg, !lv.isEmpty(), !lr.isEmpty()));
        // tocco: meta' in alto il primo torneo, meta' in basso il secondo (durante il torneo apre VGC Stats & Live)
        String uVr = vr == null ? Dati.SITO : (!lv.isEmpty() ? Dati.SITO + "#stats-vr-" + lv : vr.optString("u"));
        String uRg = rg == null ? Dati.SITO : (!lr.isEmpty() ? Dati.SITO + "#stats-reg-" + lr : rg.optString("u"));
        String u1 = vr != null ? uVr : uRg, u2 = rg != null ? uRg : uVr;
        v.setOnClickPendingIntent(R.id.tocco1, apri(c, u1, id * 10 + 1));
        v.setOnClickPendingIntent(R.id.tocco2, apri(c, u2, id * 10 + 2));
        if (largo) {
            Tema t = Tema.attuale(c);
            tema(v, t, false);
            v.setTextColor(R.id.titolo, t.box);
            JSONArray mo = w.optJSONArray("money");
            int[][] rid = {{R.id.m1, R.id.p1, R.id.n1, R.id.d1}, {R.id.m2, R.id.p2, R.id.n2, R.id.d2}, {R.id.m3, R.id.p3, R.id.n3, R.id.d3}};
            for (int i = 0; i < 3; i++) {
                JSONObject x = mo == null ? null : mo.optJSONObject(i);
                if (x == null) { v.setViewVisibility(rid[i][0], android.view.View.GONE); continue; }
                v.setViewVisibility(rid[i][0], android.view.View.VISIBLE);
                v.setTextViewText(rid[i][1], x.optString("p"));
                v.setTextViewText(rid[i][2], x.optString("n"));
                v.setTextColor(rid[i][2], t.testo);
                v.setTextColor(rid[i][3], t.tenue);
                v.setTextViewText(rid[i][3], Testo.giorno(x.optString("d")));
                v.setOnClickPendingIntent(rid[i][0], apri(c, x.optString("u"), id * 10 + 3 + i));
            }
            v.setOnClickPendingIntent(R.id.titolo, apri(c, Dati.SITO, id * 10 + 7));
        }
        m.updateAppWidget(id, v);
    }
}
