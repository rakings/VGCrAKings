package com.rakings.vgc;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.widget.RemoteViews;

import com.google.androidbrowserhelper.trusted.LauncherActivity;

import org.json.JSONArray;

/** Widget TOP 8 DEI LOCALI: le ultime 1, 2 o 3 Top 8 (si sceglie nelle impostazioni), con la squadra quando l'organizzatore l'ha pubblicata.
 *  La squadra e' scritta (solo i nomi dei Pokemon), nessuna immagine. L'elenco scorre; il tocco apre il torneo sul sito. */
public class WidgetLocali extends Base {

    static SharedPreferences imp(Context c) { return c.getSharedPreferences("lc_widget", Context.MODE_PRIVATE); }
    static int quanti(Context c, int id) { return Math.max(1, Math.min(3, imp(c).getInt("n_" + id, 1))); }

    @Override
    public void onDeleted(Context c, int[] ids) {
        SharedPreferences.Editor e = imp(c).edit();
        for (int id : ids) e.remove("n_" + id);
        e.apply();
    }

    @Override
    void disegna(Context c, AppWidgetManager m, int id) {
        JSONArray a = Dati.w(c).optJSONArray("lc");
        Tema t = Tema.attuale(c);
        RemoteViews v = new RemoteViews(c.getPackageName(), R.layout.w_lc);
        tema(v, t, true);
        v.setTextViewText(R.id.t_titolo, c.getString(R.string.w_lc));
        int k = a == null ? 0 : Math.min(quanti(c, id), a.length());
        v.setTextViewText(R.id.t_destra, "");
        v.setTextViewText(R.id.vuoto, c.getString(R.string.nessun_locale));
        v.setTextColor(R.id.vuoto, t.tenue);
        Intent s = new Intent(c, LocaliListaServizio.class);
        s.putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id);
        // indirizzo diverso per ogni stato: cosi' Android ricarica davvero l'elenco quando cambiano dati, numero o colore
        s.setData(Uri.parse("rakings://lc/" + id + "/" + k + "/" + t.id + "/" + Dati.pref(c).getLong("quando", 0)));
        v.setRemoteAdapter(R.id.lista, s);
        v.setEmptyView(R.id.lista, R.id.vuoto);
        v.setPendingIntentTemplate(R.id.lista, modello(c, id * 10 + 2));
        v.setOnClickPendingIntent(R.id.radice, apri(c, Dati.SITO, id * 10 + 1));
        m.notifyAppWidgetViewDataChanged(id, R.id.lista);
        m.updateAppWidget(id, v);
    }

    /** modello del tocco sulle righe: l'indirizzo del torneo lo mette ogni riga (per questo deve essere modificabile) */
    static PendingIntent modello(Context c, int codice) {
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setClass(c, LauncherActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        int f = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= 31 ? PendingIntent.FLAG_MUTABLE : 0);
        return PendingIntent.getActivity(c, codice, i, f);
    }
}
