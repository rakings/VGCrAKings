package com.rakings.vgc;

import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.widget.RemoteViews;

import org.json.JSONObject;

/** Widget TOP USAGE: i Pokemon piu' usati nei tornei del regolamento in corso (Top 10/20/50/100, si sceglie nelle impostazioni),
 *  con i set piu' usati: strumenti, abilita', natura e mosse. Solo testo (nessuna immagine). L'elenco scorre. */
public class WidgetUsage extends Base {

    static SharedPreferences imp(Context c) { return c.getSharedPreferences("us_widget", Context.MODE_PRIVATE); }
    static int quanti(Context c, int id) { int n = imp(c).getInt("n_" + id, 20); return n == 10 || n == 50 || n == 100 ? n : 20; }

    /** scarica il file dell'usage solo se almeno un widget Top usage e' sulla Home (fuori dal thread principale) */
    static void prepara(Context c) {
        int[] ids = AppWidgetManager.getInstance(c).getAppWidgetIds(new ComponentName(c, WidgetUsage.class));
        if (ids != null && ids.length > 0) Dati.usage(c, true);
    }

    @Override
    public void onDeleted(Context c, int[] ids) {
        SharedPreferences.Editor e = imp(c).edit();
        for (int id : ids) e.remove("n_" + id);
        e.apply();
    }

    @Override
    void disegna(Context c, AppWidgetManager m, int id) {
        JSONObject u = Dati.usage(c, false);
        Tema t = Tema.attuale(c);
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.w_lc);   // stessa struttura del widget Top 8: testata + elenco che scorre
        tema(v, t, true);
        int n = quanti(c, id);
        v.setTextViewText(R.id.t_titolo, c.getString(R.string.w_us));
        v.setTextViewText(R.id.t_destra, "Top " + n + (u == null ? "" : " · " + u.optString("reg") + " · " + c.getString(R.string.n_tornei, u.optInt("ev"))));
        v.setTextViewText(R.id.vuoto, c.getString(R.string.nessun_usage));
        v.setTextColor(R.id.vuoto, t.tenue);
        Intent s = new Intent(c, UsageListaServizio.class);
        s.putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
        s.setData(Uri.parse("rakings://us/" + id + "/" + n + "/" + t.id + "/" + Dati.pref(c).getLong("usage_quando", 0)));
        v.setRemoteAdapter(R.id.lista, s);
        v.setEmptyView(R.id.lista, R.id.vuoto);
        v.setPendingIntentTemplate(R.id.lista, apri(c, Dati.SITO, id * 10 + 2));
        v.setOnClickPendingIntent(R.id.radice, apri(c, Dati.SITO, id * 10 + 1));
        m.notifyAppWidgetViewDataChanged(id, R.id.lista);
        m.updateAppWidget(id, v);
    }
}
