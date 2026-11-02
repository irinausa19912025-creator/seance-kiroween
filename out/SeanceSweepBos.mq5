//+------------------------------------------------------------------+
//| generated from sweep_bos.json by Seance — do not edit by hand            |
//| Reads Files/seance_bars.tsv, writes Files/seance_mql5_events.tsv |
//+------------------------------------------------------------------+
#property copyright "Seance"
#property version   "1.00"

input int InpPoolLen = 20;
input int InpWindow  = 12;

int OnInit()
  {
   int fin = FileOpen("Zen\\seance_bars.tsv", FILE_READ|FILE_TXT|FILE_ANSI);
   if(fin == INVALID_HANDLE)
     { FileSave("Zen\\seance_done.txt", "FAIL no bars file"); return INIT_SUCCEEDED; }

   string  times[]; double hi[], lo[], cl[];
   int n = 0;
   while(!FileIsEnding(fin))
     {
      string line = FileReadString(fin);
      if(StringLen(line) < 5) continue;
      string p[];
      if(StringSplit(line, '\t', p) < 5) continue;
      if(p[1] == "open") continue;                       // header
      ArrayResize(times, n+1); ArrayResize(hi, n+1); ArrayResize(lo, n+1); ArrayResize(cl, n+1);
      times[n] = p[0];
      hi[n] = StringToDouble(p[2]);
      lo[n] = StringToDouble(p[3]);
      cl[n] = StringToDouble(p[4]);
      n++;
     }
   FileClose(fin);

   int fout = FileOpen("Zen\\seance_mql5_events.tsv", FILE_WRITE|FILE_TXT|FILE_ANSI);
   int pside = 0, pbar = -1; double phi = 0, plo = 0;
   int evcount = 0;
   for(int k = 0; k < n; k++)
     {
      if(pside != 0)
        {
         if(pside == 1)
           {
            if(hi[k] > phi)        { FileWriteString(fout, times[k] + "\tCANCEL\n"); pside = 0; evcount++; }
            else if(cl[k] < plo)   { FileWriteString(fout, times[k] + "\tBOS\n");    pside = 0; evcount++; }
            else if(k - pbar >= InpWindow) { FileWriteString(fout, times[k] + "\tEXPIRE\n"); pside = 0; evcount++; }
           }
         else
           {
            if(lo[k] < plo)        { FileWriteString(fout, times[k] + "\tCANCEL\n"); pside = 0; evcount++; }
            else if(cl[k] > phi)   { FileWriteString(fout, times[k] + "\tBOS\n");    pside = 0; evcount++; }
            else if(k - pbar >= InpWindow) { FileWriteString(fout, times[k] + "\tEXPIRE\n"); pside = 0; evcount++; }
           }
        }
      if(k >= InpPoolLen)
        {
         double ph = hi[k-InpPoolLen], pl = lo[k-InpPoolLen];
         for(int j = k-InpPoolLen; j < k; j++)
           { if(hi[j] > ph) ph = hi[j]; if(lo[j] < pl) pl = lo[j]; }
         bool sh = (hi[k] > ph && cl[k] <= ph);
         bool sl = (lo[k] < pl && cl[k] >= pl);
         if(sh && !sl) { FileWriteString(fout, times[k] + "\tSWEEP_HIGH\n"); pside = 1; pbar = k; phi = hi[k]; plo = lo[k]; evcount++; }
         else if(sl && !sh) { FileWriteString(fout, times[k] + "\tSWEEP_LOW\n"); pside = 2; pbar = k; phi = hi[k]; plo = lo[k]; evcount++; }
        }
     }
   FileClose(fout);
   FileSave("Zen\\seance_done.txt", "OK bars=" + IntegerToString(n) + " events=" + IntegerToString(evcount));
   return INIT_SUCCEEDED;
  }

void FileSave(string fn, string txt)
  {
   int f = FileOpen(fn, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(f != INVALID_HANDLE) { FileWriteString(f, txt + "\n"); FileClose(f); }
  }

void OnTick() {}
void OnDeinit(const int r) {}
