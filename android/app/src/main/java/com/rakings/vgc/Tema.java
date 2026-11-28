package com.rakings.vgc;

import android.content.Context;

/** Colori dei widget: gli stessi temi dell'app. Si sceglie nelle impostazioni del widget e vale per tutti i widget. Predefinito: Nero. */
final class Tema {
    final String id; final int nome, fondo, riquadro, pallino; final boolean chiaro; final int accento, box;
    final int testo, tenue, linea;
    int alfa = 255;   // opacita' dello sfondo dei widget (0-255), dalle impostazioni
    Tema(String id, int nome, int fondo, int riquadro, int pallino, boolean chiaro, int accento, int box) {
        this.id = id; this.nome = nome; this.fondo = fondo; this.riquadro = riquadro; this.pallino = pallino; this.chiaro = chiaro;
        this.accento = accento; this.box = box;
        this.testo = chiaro ? 0xFF2A0D10 : 0xFFFFF1EF;
        this.tenue = chiaro ? 0xFF7A4A4F : 0xFFE0AAA6;
        this.linea = chiaro ? 0x22000000 : 0x18FFFFFF;
    }

    static final Tema[] TUTTI = {
        new Tema("nerorosso", R.string.t_nero_def, R.drawable.fw_nerorosso, R.drawable.fb_ffd21f, R.drawable.ft_nerorosso, false, 0xFFFF8AA0, 0xFFFFD21F),
        new Tema("rossodef", R.string.t_rosso, R.drawable.fw_rossodef, R.drawable.fb_ffd21f, R.drawable.ft_rossodef, false, 0xFFFF8AA0, 0xFFFFD21F),
        new Tema("chiaro", R.string.t_chiaro, R.drawable.fw_chiaro, R.drawable.fb_e11d2e, R.drawable.ft_chiaro, true, 0xFFE11D2E, 0xFFE11D2E),
        new Tema("rosso", R.string.t_rossoscuro, R.drawable.fw_rosso, R.drawable.fb_ffd21f, R.drawable.ft_rosso, false, 0xFFFF8AA0, 0xFFFFD21F),
        new Tema("blu", R.string.t_blu, R.drawable.fw_blu, R.drawable.fb_ffd21f, R.drawable.ft_blu, false, 0xFF60A5FA, 0xFFFFD21F),
        new Tema("viola", R.string.t_viola, R.drawable.fw_viola, R.drawable.fb_ffd21f, R.drawable.ft_viola, false, 0xFFC084FC, 0xFFFFD21F),
        new Tema("violaprofondo", R.string.t_violap, R.drawable.fw_violaprofondo, R.drawable.fb_ffd21f, R.drawable.ft_violaprofondo, false, 0xFFA78BFA, 0xFFFFD21F),
        new Tema("verde", R.string.t_verde, R.drawable.fw_verde, R.drawable.fb_ffd21f, R.drawable.ft_verde, false, 0xFF22C55E, 0xFFFFD21F),
        new Tema("oro", R.string.t_oro, R.drawable.fw_oro, R.drawable.fb_ffd21f, R.drawable.ft_oro, false, 0xFFF59E0B, 0xFFFFD21F),
        new Tema("giallochiaro", R.string.t_giallo, R.drawable.fw_giallochiaro, R.drawable.fb_a16207, R.drawable.ft_giallochiaro, true, 0xFFA16207, 0xFFA16207),
        new Tema("giallo", R.string.t_giallonero, R.drawable.fw_giallo, R.drawable.fb_ffd21f, R.drawable.ft_giallo, false, 0xFFFACC15, 0xFFFFD21F),
        new Tema("nero", R.string.t_nerogrigio, R.drawable.fw_nero, R.drawable.fb_ffd21f, R.drawable.ft_nero, false, 0xFFE5E7EB, 0xFFFFD21F),
        new Tema("onice", R.string.t_onice, R.drawable.fw_onice, R.drawable.fb_ffd21f, R.drawable.ft_onice, false, 0xFFD4D4D8, 0xFFFFD21F),
        new Tema("ghiaccio", R.string.t_ghiaccio, R.drawable.fw_ghiaccio, R.drawable.fb_0284c7, R.drawable.ft_ghiaccio, true, 0xFF0284C7, 0xFF0284C7)
    };

    static Tema attuale(Context c) {
        android.content.SharedPreferences p = c.getSharedPreferences("tema_widget", Context.MODE_PRIVATE);
        String id = p.getString("id", "nerorosso");
        Tema s = TUTTI[0];
        for (Tema t : TUTTI) if (t.id.equals(id)) { s = t; break; }
        s.alfa = Math.round(255 * (100 - trasparenza(c)) / 100f);
        return s;
    }

    /** trasparenza dello sfondo di tutti i widget, in percentuale (0 = pieno, massimo 80) */
    static int trasparenza(Context c) {
        return Math.max(0, Math.min(80, c.getSharedPreferences("tema_widget", Context.MODE_PRIVATE).getInt("trasp", 0)));
    }

    static void scegliTrasparenza(Context c, int perc) {
        c.getSharedPreferences("tema_widget", Context.MODE_PRIVATE).edit().putInt("trasp", Math.max(0, Math.min(80, perc))).apply();
    }

    static void scegli(Context c, String id) {
        c.getSharedPreferences("tema_widget", Context.MODE_PRIVATE).edit().putString("id", id).apply();
    }
}
