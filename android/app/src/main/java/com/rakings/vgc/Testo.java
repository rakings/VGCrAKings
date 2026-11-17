package com.rakings.vgc;

import android.content.Context;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Piccole cose di lingua: posizione (7° posto / 7th place ...), date corte nella lingua del telefono. */
final class Testo {
    static String lingua() { return Locale.getDefault().getLanguage(); }

    static String ordinale(int n) {
        switch (lingua()) {
            case "it": return n + "°";
            case "en": { int v = n % 100; String s = (v >= 11 && v <= 13) ? "th" : n % 10 == 1 ? "st" : n % 10 == 2 ? "nd" : n % 10 == 3 ? "rd" : "th"; return n + s; }
            case "es": return n + ".º";
            case "pt": return n + "º";
            case "fr": return n + (n == 1 ? "er" : "e");
            case "de": return "Platz " + n;
            case "ja": return n + "位";
            case "ko": return n + "위";
            default: return "#" + n;
        }
    }

    static String posto(Context c, int n) { return c.getString(R.string.posto, ordinale(n)); }

    private static Date data(String iso) {
        try {
            SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd", Locale.US);
            return f.parse(iso);
        } catch (Exception e) { return null; }
    }

    /** «20–22 nov», «5 dic», «Nov 20–22» secondo la lingua */
    static String intervallo(String da, String a) {
        Date d1 = data(da), d2 = (a == null || a.isEmpty() || a.equals(da)) ? null : data(a);
        if (d1 == null) return da == null ? "" : da;
        String sk = android.text.format.DateFormat.getBestDateTimePattern(Locale.getDefault(), "dMMM");
        SimpleDateFormat f = new SimpleDateFormat(sk, Locale.getDefault());
        if (d2 == null) return f.format(d1);
        SimpleDateFormat m = new SimpleDateFormat("M", Locale.US);
        if (m.format(d1).equals(m.format(d2))) {
            String g1 = new SimpleDateFormat("d", Locale.US).format(d1);
            String fd2 = f.format(d2);
            String g2 = new SimpleDateFormat("d", Locale.US).format(d2);
            // sostituisce il giorno della seconda data con «20–22»
            int i = fd2.indexOf(g2);
            if (i >= 0) return fd2.substring(0, i) + g1 + "–" + g2 + fd2.substring(i + g2.length());
        }
        return f.format(d1) + " – " + f.format(d2);
    }

    static String giorno(String iso) { return intervallo(iso, null); }
}
