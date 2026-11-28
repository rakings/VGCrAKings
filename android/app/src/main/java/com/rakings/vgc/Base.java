package com.rakings.vgc;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;

import com.google.androidbrowserhelper.trusted.LauncherActivity;

/** Parte comune dei widget: un solo download aggiorna tutti i widget (Tornei, CP bar, Bacheca, Top 8 dei locali, Top usage, Calendario). */
abstract class Base extends AppWidgetProvider {

    abstract void disegna(Context c, AppWidgetManager m, int id);

    @Override
    public void onUpdate(Context c, AppWidgetManager m, int[] ids) {
        for (int id : ids) disegna(c, m, id);            // subito con i dati salvati
        final PendingResult pr = goAsync();
        final Context app = c.getApplicationContext();
        new Thread(() -> {
            try {
                Dati.aggiorna(app, false);
                WidgetBacheca.scaricaImmagini(app);
                WidgetCp.preparaGiocatori(app);
                WidgetUsage.prepara(app);
                ridisegnaTutti(app);
            } finally { pr.finish(); }
        }).start();
    }

    @Override
    public void onAppWidgetOptionsChanged(Context c, AppWidgetManager m, int id, Bundle o) {
        disegna(c, m, id);   // cambiata la dimensione: cambia il formato
    }

    static void ridisegnaTutti(Context c) {
        AppWidgetManager m = AppWidgetManager.getInstance(c);
        for (Base b : new Base[]{new WidgetTornei(), new WidgetCp(), new WidgetBacheca(), new WidgetLocali(), new WidgetUsage(), new WidgetCalendario()}) {
            int[] ids = m.getAppWidgetIds(new ComponentName(c, b.getClass()));
            for (int id : ids) b.disegna(c, m, id);
        }
    }

    /** larghezza e altezza del widget in dp (telefono in verticale) */
    static int[] misura(AppWidgetManager m, int id) {
        Bundle o = m.getAppWidgetOptions(id);
        int w = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        int h = o.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 110);
        if (w <= 0) w = 250;
        if (h <= 0) h = 110;
        return new int[]{w, h};
    }

    /** colori del tema sulla testata (uovo + titolo) e sul fondo del widget */
    static void tema(android.widget.RemoteViews v, Tema t, boolean testata) {
        v.setImageViewResource(R.id.sfondo, t.fondo);
        v.setInt(R.id.sfondo, "setImageAlpha", t.alfa);   // trasparenza scelta nelle impostazioni (vale per tutti i widget)
        if (testata) { v.setTextColor(R.id.t_titolo, t.accento); v.setTextColor(R.id.t_destra, t.tenue); }
    }

    /** tocco: apre l'app (il sito) su quell'indirizzo */
    static PendingIntent apri(Context c, String url, int codice) {
        Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url == null || url.isEmpty() ? Dati.SITO : url));
        i.setClass(c, LauncherActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        return PendingIntent.getActivity(c, codice, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
}
