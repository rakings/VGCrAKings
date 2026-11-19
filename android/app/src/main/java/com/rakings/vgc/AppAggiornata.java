package com.rakings.vgc;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Dopo l'installazione di una versione nuova sopra la vecchia Android non ridisegna da solo
 *  i widget gia' messi: restano col disegno vecchio fino al giro dei 30 minuti. Qui li ridisegniamo subito e scarichiamo i dati. */
public class AppAggiornata extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        String a = i.getAction();
        if (!Intent.ACTION_MY_PACKAGE_REPLACED.equals(a)) return;
        final Context app = c.getApplicationContext();
        Base.ridisegnaTutti(app);                         // subito con i dati salvati
        final PendingResult pr = goAsync();
        new Thread(() -> {
            try {
                Dati.aggiorna(app, false);
                WidgetBacheca.scaricaImmagini(app);
                WidgetCp.preparaGiocatori(app);
                WidgetUsage.prepara(app);
                Base.ridisegnaTutti(app);
            } catch (Exception ignorata) {
            } finally { pr.finish(); }
        }).start();
    }
}
