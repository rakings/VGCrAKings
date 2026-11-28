package com.rakings.vgc;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.widget.RemoteViews;

import org.json.JSONObject;

import java.util.Calendar;
import java.util.TimeZone;

/** Widget CALENDARIO: il mese con i pallini dei tornei (come il calendario del sito), frecce ‹ › per cambiare mese,
 *  LIVE sul giorno di oggi quando c'e' un Regionale o un VR in corso. Tocco su un giorno: apre il calendario dell'app su quel giorno
 *  (oggi, durante il torneo, apre VGC Stats & Live). Impostazioni per widget: tipi da nascondere (Money, VR e Regionali sempre visibili),
 *  primo giorno della settimana, legenda, ritorno da solo al mese corrente. */
public class WidgetCalendario extends Base {
    static final String MESE = "com.rakings.vgc.CAL_MESE", TORNA = "com.rakings.vgc.CAL_TORNA";
    static final long ATTESA = 5 * 60 * 1000L;   // dopo 5 minuti senza toccare le frecce torna al mese corrente (se attivo)
    private static final int BASE = 1_000_000;   // codici dei tocchi, separati da quelli degli altri widget

    static SharedPreferences imp(Context c) { return c.getSharedPreferences("cal_widget", Context.MODE_PRIVATE); }
    static String spenti(Context c, int id) { return imp(c).getString("spenti_" + id, ""); }
    static boolean lunedi(Context c, int id) { return imp(c).getBoolean("lun_" + id, true); }
    static boolean legenda(Context c, int id) { return imp(c).getBoolean("leg_" + id, true); }
    static boolean auto(Context c, int id) { return imp(c).getBoolean("auto_" + id, true); }

    @Override
    public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (MESE.equals(a) || TORNA.equals(a)) {
            int id = i.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID);
            if (id == AppWidgetManager.INVALID_APPWIDGET_ID) return;
            if (MESE.equals(a)) {
                int d = i.getIntExtra("d", 0);
                SharedPreferences p = imp(c);
                int off = Math.max(-12, Math.min(18, p.getInt("off_" + id, 0) + d));
                p.edit().putInt("off_" + id, off).putLong("ts_" + id, System.currentTimeMillis()).apply();
                if (auto(c, id) && off != 0) programmaRitorno(c, id);
            }
            disegna(c, AppWidgetManager.getInstance(c), id);
            return;
        }
        super.onReceive(c, i);
    }

    @Override
    public void onDeleted(Context c, int[] ids) {
        SharedPreferences.Editor e = imp(c).edit();
        for (int id : ids) e.remove("spenti_" + id).remove("lun_" + id).remove("leg_" + id).remove("auto_" + id).remove("off_" + id).remove("ts_" + id);
        e.apply();
    }

    @Override
    void disegna(Context c, AppWidgetManager m, int id) {
        SharedPreferences p = imp(c);
        int off = p.getInt("off_" + id, 0);
        if (off != 0 && auto(c, id) && System.currentTimeMillis() - p.getLong("ts_" + id, 0) >= ATTESA) {
            off = 0;
            p.edit().putInt("off_" + id, 0).apply();
        }
        // mese da mostrare (ora italiana, come il resto del sito)
        Calendar k = Calendar.getInstance(TimeZone.getTimeZone("Europe/Rome"));
        k.set(Calendar.DAY_OF_MONTH, 1);
        k.add(Calendar.MONTH, off);
        int anno = k.get(Calendar.YEAR), mese = k.get(Calendar.MONTH);
        boolean lun = lunedi(c, id), leg = legenda(c, id);
        String oggi = Dati.oggi();

        JSONObject w = Dati.w(c);
        SharedPreferences dp = Dati.pref(c);
        String lr = dp.getString("live_rg", ""), lv = dp.getString("live_vr", "");
        boolean live = !lr.isEmpty() || !lv.isEmpty();
        String uLive = !lr.isEmpty() ? Dati.SITO + "#stats-reg-" + lr : Dati.SITO + "#stats-vr-" + lv;

        int righe = DisegnoCal.settimane(anno, mese, lun);
        int lay = righe <= 4 ? (leg ? R.layout.w_cal_4l : R.layout.w_cal_4) : righe == 5 ? (leg ? R.layout.w_cal_5l : R.layout.w_cal_5) : (leg ? R.layout.w_cal_6l : R.layout.w_cal_6);
        RemoteViews v = new RemoteViews(c.getPackageName(), lay);

        int[] mis = misura(m, id);
        float dens = c.getResources().getDisplayMetrics().density, sc = Math.min(dens, 2.25f);
        int W = (int) (Math.max(110, Math.min(mis[0], 600)) * sc), H = (int) (Math.max(110, Math.min(mis[1], 700)) * sc);
        Tema t = Tema.attuale(c);
        v.setImageViewBitmap(R.id.cal, DisegnoCal.disegna(c, W, H, sc, t, anno, mese, lun, spenti(c, id), leg, w.optJSONObject("cal"), oggi, live));

        // tocchi
        String primo = DisegnoCal.iso(anno, mese, 1);
        String uMese = Dati.SITO + "#cal-" + (off == 0 ? oggi : primo);
        v.setOnClickPendingIntent(R.id.prima, cambia(c, id, -1));
        v.setOnClickPendingIntent(R.id.dopo, cambia(c, id, 1));
        v.setOnClickPendingIntent(R.id.mese, apri(c, uMese, BASE + id * 100 + 3));
        if (leg) v.setOnClickPendingIntent(R.id.legenda, apri(c, uMese, BASE + id * 100 + 4));
        int vuote = DisegnoCal.vuote(anno, mese, lun), dim = DisegnoCal.giorniMese(anno, mese);
        for (int i = 0; i < righe * 7 && i < CELLE.length; i++) {
            int g = i - vuote + 1;
            String u;
            if (g < 1 || g > dim) u = uMese;
            else {
                String d = DisegnoCal.iso(anno, mese, g);
                u = live && d.equals(oggi) ? uLive : Dati.SITO + "#cal-" + d;
            }
            v.setOnClickPendingIntent(CELLE[i], apri(c, u, BASE + id * 100 + 10 + i));
        }
        m.updateAppWidget(id, v);
    }

    static PendingIntent cambia(Context c, int id, int d) {
        Intent i = new Intent(c, WidgetCalendario.class).setAction(MESE)
                .putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id).putExtra("d", d)
                .setData(Uri.parse("rakings://cal/" + id + "/" + d));   // un intent diverso per ogni widget e freccia
        return PendingIntent.getBroadcast(c, BASE + id * 100 + (d > 0 ? 2 : 1), i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    /** sveglia non precisa (nessun permesso): ridisegna il widget quando e' ora di tornare al mese corrente */
    static void programmaRitorno(Context c, int id) {
        try {
            Intent i = new Intent(c, WidgetCalendario.class).setAction(TORNA)
                    .putExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, id).setData(Uri.parse("rakings://cal/" + id + "/torna"));
            PendingIntent pi = PendingIntent.getBroadcast(c, BASE + id * 100 + 90, i, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            AlarmManager am = (AlarmManager) c.getSystemService(Context.ALARM_SERVICE);
            if (am != null) am.set(AlarmManager.RTC, System.currentTimeMillis() + ATTESA + 2000, pi);
        } catch (Exception ignorata) { }
    }

    static final int[] CELLE = {
        R.id.c0, R.id.c1, R.id.c2, R.id.c3, R.id.c4, R.id.c5, R.id.c6,
        R.id.c7, R.id.c8, R.id.c9, R.id.c10, R.id.c11, R.id.c12, R.id.c13,
        R.id.c14, R.id.c15, R.id.c16, R.id.c17, R.id.c18, R.id.c19, R.id.c20,
        R.id.c21, R.id.c22, R.id.c23, R.id.c24, R.id.c25, R.id.c26, R.id.c27,
        R.id.c28, R.id.c29, R.id.c30, R.id.c31, R.id.c32, R.id.c33, R.id.c34,
        R.id.c35, R.id.c36, R.id.c37, R.id.c38, R.id.c39, R.id.c40, R.id.c41
    };
}
