object_event_add(WinBanner, ev_create, 0, "
    if (global.nextMap = 'koth_random') {
        //run mapgenerator.exe with no arguments
        execute_shell('mapgenerator.pyw','');
        alarm[0] = 5 * 30 * global.delta_factor;
    }
    else if (global.nextMap = 'cp_random') {
        //run mapgenerator.exe with cp
        execute_shell('mapgenerator.pyw','CP');
        alarm[0] = 5 * 30 * global.delta_factor;
    }
");

object_event_add(WinBanner, ev_alarm, 0, "
    if((global.isHost == true) && ((global.nextMap = 'koth_random') || (global.nextMap = 'cp_random'))) {
        if (file_exists('randomname.gg2')) {
            var nextRandom, nextRandomFile;

            nextRandomFile = file_text_open_read('randomname.gg2');
            nextRandom = file_text_read_string(nextRandomFile);
            file_text_close(nextRandomFile);

            if (file_exists('Maps/' + nextRandom + '.png')) {
                global.nextMap = nextRandom;
            } else {
                global.nextMap = 'koth_harvest';
            }
        } else {
            global.nextMap = 'koth_harvest';
        }
    }
");