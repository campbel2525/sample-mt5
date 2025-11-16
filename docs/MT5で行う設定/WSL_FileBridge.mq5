//+------------------------------------------------------------------+
//|                                                   WSL_FileBridge |
//|                        File-IPC bridge for MT5/WSL/Docker (MA/RSI対応)|
//| - Common\Files の命令ファイルを読み、応答やCSVを書き出すEA          |
//| - DLL不要 / FW不要。SYMBOL_INFO_TICK / ORDER_SEND                 |
//|   に加えて GET_MA_LATEST / COPY_MA(ローソク+MA+RSI全部入り)を実装
// time,open,high,low,close,tick_volume,spread,real_volume,moving_average_short,moving_average_middle,moving_average_long,rsi
//+------------------------------------------------------------------+
#property strict

//==== 設定（Common\Files直下の命令ファイル名） ====//
input string CMD_FILE_NAME = "mt5_cmd.txt"; // Python側と一致させる

// 応答ファイル: "mt5_resp_<id>.txt"
// データCSV   : "mt5_bars_<id>.csv"  （ローソク＋MA＋RSI）

//================ ユーティリティ ================//
string Trim(const string s)
{
   string t = s;
   StringTrimLeft(t);
   StringTrimRight(t);
   return t;
}

bool ParseLine(const string line, string &key, string &value)
{
   int pos = StringFind(line, "=");
   if(pos < 0) return false;
   key   = Trim(StringSubstr(line, 0, pos));
   value = Trim(StringSubstr(line, pos + 1));
   return true;
}

string RespFileName(const string id)
{
   return "mt5_resp_" + id + ".txt";
}

//---- 応答共通 ----//
void WriteResponseError(const string id, const string message, const int code=0)
{
   int h = FileOpen(RespFileName(id), FILE_WRITE|FILE_COMMON|FILE_ANSI);
   if(h==INVALID_HANDLE)
   {
      Print("resp(error) open failed id=",id," err=",GetLastError());
      return;
   }
   FileWriteString(h, "ok=false\r\n");
   FileWriteString(h, "id="+id+"\r\n");
   FileWriteString(h, "error="+message+"\r\n");
   if(code!=0) FileWriteString(h, "code="+(string)code+"\r\n");
   FileClose(h);
}

void WriteResponseOK_Tick(const string id, const MqlTick &tick, const string symbol)
{
   int h = FileOpen(RespFileName(id), FILE_WRITE|FILE_COMMON|FILE_ANSI);
   if(h==INVALID_HANDLE)
   {
      Print("resp(tick) open failed id=",id," err=",GetLastError());
      return;
   }
   FileWriteString(h, "ok=true\r\n");
   FileWriteString(h, "id="+id+"\r\n");
   FileWriteString(h, "symbol="+symbol+"\r\n");
   FileWriteString(h, "bid="+DoubleToString(tick.bid,_Digits)+"\r\n");
   FileWriteString(h, "ask="+DoubleToString(tick.ask,_Digits)+"\r\n");
   FileWriteString(h, "last="+DoubleToString(tick.last,_Digits)+"\r\n");
   FileWriteString(h, "time="+(string)tick.time+"\r\n"); // POSIX秒
   FileClose(h);
}

void WriteResponseOK_Order(const string id, const ulong ticket, const int retcode, const double price)
{
   int h = FileOpen(RespFileName(id), FILE_WRITE|FILE_COMMON|FILE_ANSI);
   if(h==INVALID_HANDLE)
   {
      Print("resp(order) open failed id=",id," err=",GetLastError());
      return;
   }
   FileWriteString(h, "ok=true\r\n");
   FileWriteString(h, "id="+id+"\r\n");
   FileWriteString(h, "ticket="+(string)ticket+"\r\n");
   FileWriteString(h, "retcode="+(string)retcode+"\r\n");
   FileWriteString(h, "price="+DoubleToString(price,_Digits)+"\r\n");
   FileClose(h);
}

void WriteResponseOK_MA_Latest(const string id, const string symbol, const string timeframe,
                               const int pS, const int pM, const int pL,
                               const string method, const string price,
                               const double maS, const double maM, const double maL,
                               const datetime bar_time, const double close_price)
{
   int h = FileOpen(RespFileName(id), FILE_WRITE|FILE_COMMON|FILE_ANSI);
   if(h==INVALID_HANDLE)
   {
      Print("resp(ma_latest) open failed id=",id," err=",GetLastError());
      return;
   }
   FileWriteString(h, "ok=true\r\n");
   FileWriteString(h, "id="+id+"\r\n");
   FileWriteString(h, "symbol="+symbol+"\r\n");
   FileWriteString(h, "timeframe="+timeframe+"\r\n");
   FileWriteString(h, "period_short="+(string)pS+"\r\n");
   FileWriteString(h, "period_middle="+(string)pM+"\r\n");
   FileWriteString(h, "period_long="+(string)pL+"\r\n");
   FileWriteString(h, "method="+method+"\r\n");
   FileWriteString(h, "applied_price="+price+"\r\n");
   FileWriteString(h, "ma_short="+DoubleToString(maS,_Digits)+"\r\n");
   FileWriteString(h, "ma_middle="+DoubleToString(maM,_Digits)+"\r\n");
   FileWriteString(h, "ma_long="+DoubleToString(maL,_Digits)+"\r\n");
   FileWriteString(h, "bar_time="+(string)bar_time+"\r\n");
   FileWriteString(h, "close="+DoubleToString(close_price,_Digits)+"\r\n");
   FileClose(h);
}

//---- 文字列→ENUM: timeframe ----//
bool StrToTimeframe(const string s, ENUM_TIMEFRAMES &tf)
{
   string u=s;
   StringToUpper(u);
   if(u=="M1"){tf=PERIOD_M1;return true;}
   if(u=="M5"){tf=PERIOD_M5;return true;}
   if(u=="M15"){tf=PERIOD_M15;return true;}
   if(u=="M30"){tf=PERIOD_M30;return true;}
   if(u=="H1"){tf=PERIOD_H1;return true;}
   if(u=="H4"){tf=PERIOD_H4;return true;}
   if(u=="D1"){tf=PERIOD_D1;return true;}
   if(u=="W1"){tf=PERIOD_W1;return true;}
   if(u=="MN1"){tf=PERIOD_MN1;return true;}
   return false;
}

//---- 文字列→ENUM: MAメソッド ----//
bool StrToMaMethod(const string s, ENUM_MA_METHOD &m, string &norm)
{
   string u=s;
   StringToUpper(u);
   if(u=="SMA" || u=="MODE_SMA"){ m=MODE_SMA; norm="SMA"; return true; }
   if(u=="EMA" || u=="MODE_EMA"){ m=MODE_EMA; norm="EMA"; return true; }
   if(u=="SMMA"|| u=="MODE_SMMA"){ m=MODE_SMMA; norm="SMMA"; return true; }
   if(u=="LWMA"|| u=="MODE_LWMA"){ m=MODE_LWMA; norm="LWMA"; return true; }
   return false;
}

//---- 文字列→ENUM: 適用価格 ----//
bool StrToAppliedPrice(const string s, ENUM_APPLIED_PRICE &ap, string &norm)
{
   string u=s;
   StringToUpper(u);
   if(u=="" || u=="CLOSE" || u=="PRICE_CLOSE"){ ap=PRICE_CLOSE; norm="CLOSE"; return true; }
   if(u=="OPEN"  || u=="PRICE_OPEN"){ ap=PRICE_OPEN; norm="OPEN"; return true; }
   if(u=="HIGH"  || u=="PRICE_HIGH"){ ap=PRICE_HIGH; norm="HIGH"; return true; }
   if(u=="LOW"   || u=="PRICE_LOW"){  ap=PRICE_LOW;  norm="LOW";  return true; }
   if(u=="MEDIAN"|| u=="PRICE_MEDIAN"){ ap=PRICE_MEDIAN; norm="MEDIAN"; return true; }
   if(u=="TYPICAL"||u=="PRICE_TYPICAL"){ ap=PRICE_TYPICAL; norm="TYPICAL"; return true; }
   if(u=="WEIGHTED"||u=="PRICE_WEIGHTED"){ ap=PRICE_WEIGHTED; norm="WEIGHTED"; return true; }
   return false;
}

//---- 文字列→ENUM: 注文タイプ ----//
bool StrToOrderType(const string s, ENUM_ORDER_TYPE &ot)
{
   string u=s;
   StringToUpper(u);
   if(u=="BUY")  { ot=ORDER_TYPE_BUY;  return true; }
   if(u=="SELL") { ot=ORDER_TYPE_SELL; return true; }
   return false;
}

//---- 全部入り CSV（ローソク＋MA＋RSI） ----//
string WriteBarsFullCsv(const string id,
                        const MqlRates &rates[],
                        const double &maS[],
                        const double &maM[],
                        const double &maL[],
                        const double &rsi[],
                        const int count)
{
   string fname="mt5_bars_"+id+".csv";
   int h=FileOpen(fname, FILE_WRITE|FILE_COMMON|FILE_ANSI);
   if(h==INVALID_HANDLE)
   {
      Print("bars(full) csv open failed id=",id," err=",GetLastError());
      return "";
   }

   FileWriteString(h,
      "time,open,high,low,close,tick_volume,spread,real_volume,"
      "moving_average_short,moving_average_middle,moving_average_long,rsi\r\n");

   for(int i=0;i<count;i++)
   {
      string line=(string)rates[i].time+","+
         DoubleToString(rates[i].open,_Digits)+","+
         DoubleToString(rates[i].high,_Digits)+","+
         DoubleToString(rates[i].low,_Digits)+","+
         DoubleToString(rates[i].close,_Digits)+","+
         (string)rates[i].tick_volume+","+
         (string)rates[i].spread+","+
         (string)rates[i].real_volume+","+
         DoubleToString(maS[i],_Digits)+","+
         DoubleToString(maM[i],_Digits)+","+
         DoubleToString(maL[i],_Digits)+","+
         DoubleToString(rsi[i],_Digits)+"\r\n";
      FileWriteString(h,line);
   }
   FileClose(h);
   return fname;
}

//================ ライフサイクル ================//
int OnInit()
{
   EventSetTimer(1);
   Print("WSL_FileBridge started. CommonFiles=",
         TerminalInfoString(TERMINAL_COMMONDATA_PATH), "\\Files\\");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTick()
{
   // ポーリングは OnTimer で実施
}

void OnTimer()
{
   if(FileIsExist(CMD_FILE_NAME, FILE_COMMON))
      ProcessCommand();
}

//================ メイン処理 ================//
void ProcessCommand()
{
   int h=FileOpen(CMD_FILE_NAME,
                  FILE_READ|FILE_COMMON|FILE_ANSI|
                  FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(h==INVALID_HANDLE)
   {
      Print("CMD open failed err=",GetLastError());
      return;
   }

   // 受け取りパラメータ（既定値つき）
   string id="", action="", symbol="", type_s="", comment="";
   string timeframe_s="M1", method_s="SMA", price_s="CLOSE";
   int    period_short=5, period_middle=20, period_long=60;
   int    period_rsi=14;
   int    deviation=10, count=300, ma_shift=1; // ma_shift は GET_MA_LATEST 用
   double volume=0.0, sl=0.0, tp=0.0;

   while(!FileIsEnding(h))
   {
      string line=FileReadString(h);
      string k,v;
      if(!ParseLine(line,k,v)) continue;

      if(k=="id") id=v;
      else if(k=="action") action=v;
      else if(k=="symbol") symbol=v;
      else if(k=="type") type_s=v;
      else if(k=="volume") volume=StringToDouble(v);
      else if(k=="sl") sl=StringToDouble(v);
      else if(k=="tp") tp=StringToDouble(v);
      else if(k=="deviation") deviation=(int)StringToInteger(v);
      else if(k=="comment") comment=v;

      else if(k=="timeframe") timeframe_s=v;
      else if(k=="count")     count=(int)StringToInteger(v);

      else if(k=="period_short")  period_short=(int)StringToInteger(v);
      else if(k=="period_middle") period_middle=(int)StringToInteger(v);
      else if(k=="period_long")   period_long=(int)StringToInteger(v);
      else if(k=="period_rsi")    period_rsi=(int)StringToInteger(v);
      else if(k=="method")        method_s=v;    // SMA/EMA/SMMA/LWMA
      else if(k=="applied_price") price_s=v;     // CLOSE/OPEN/HIGH/...
      else if(k=="ma_shift")      ma_shift=(int)StringToInteger(v); // 0=未確定/1=確定
   }
   FileClose(h);

   // 再処理防止
   if(!FileDelete(CMD_FILE_NAME, FILE_COMMON))
      Print("CMD delete warn err=",GetLastError());

   if(id=="")
   {
      WriteResponseError("unknown","missing id");
      return;
   }
   if(action=="")
   {
      WriteResponseError(id,"missing action");
      return;
   }

   StringToUpper(action);

   //--- ティック取得
   if(action=="SYMBOL_INFO_TICK")
   {
      if(symbol=="")
      {
         WriteResponseError(id,"missing symbol");
         return;
      }
      MqlTick t;
      if(!SymbolInfoTick(symbol,t))
      {
         WriteResponseError(id,"SymbolInfoTick failed",(int)GetLastError());
         return;
      }
      WriteResponseOK_Tick(id,t,symbol);
      return;
   }
   //--- 成行注文
   else if(action=="ORDER_SEND")
   {
      if(symbol==""||type_s==""||volume<=0.0)
      {
         WriteResponseError(id,"missing symbol/type/volume");
         return;
      }
      ENUM_ORDER_TYPE ot;
      if(!StrToOrderType(type_s, ot))
      {
         WriteResponseError(id,"unknown order type");
         return;
      }

      MqlTick t;
      if(!SymbolInfoTick(symbol,t))
      {
         WriteResponseError(id,"SymbolInfoTick failed",(int)GetLastError());
         return;
      }

      MqlTradeRequest req;
      MqlTradeResult  res;
      ZeroMemory(req);
      ZeroMemory(res);
      req.action   = TRADE_ACTION_DEAL;
      req.symbol   = symbol;
      req.type     = ot;
      req.volume   = volume;
      req.deviation= deviation;
      req.comment  = comment;
      req.price    = (ot==ORDER_TYPE_BUY ? t.ask : t.bid);
      if(sl>0) req.sl=sl;
      if(tp>0) req.tp=tp;

      if(!OrderSend(req,res))
      {
         WriteResponseError(id,"OrderSend() failed",(int)GetLastError());
         return;
      }
      WriteResponseOK_Order(id,res.order,res.retcode,req.price);
      return;
   }
   //--- 最新MA値（短/中/長）を返す
   else if(action=="GET_MA_LATEST")
   {
      if(symbol=="")
      {
         WriteResponseError(id,"missing symbol");
         return;
      }
      ENUM_TIMEFRAMES tf;
      if(!StrToTimeframe(timeframe_s, tf))
      {
         WriteResponseError(id,"bad timeframe: "+timeframe_s);
         return;
      }
      ENUM_MA_METHOD mm;
      string         method_norm="";
      if(!StrToMaMethod(method_s, mm, method_norm))
      {
         WriteResponseError(id,"bad method: "+method_s);
         return;
      }
      ENUM_APPLIED_PRICE ap;
      string             price_norm="";
      if(!StrToAppliedPrice(price_s, ap, price_norm))
      {
         WriteResponseError(id,"bad applied_price: "+price_s);
         return;
      }

      if(period_short<=0)  period_short=5;
      if(period_middle<=0) period_middle=20;
      if(period_long<=0)   period_long=60;
      if(ma_shift<0)       ma_shift=1; // 既定は確定バー

      int hS=iMA(symbol, tf, period_short, 0, mm, ap);
      int hM=iMA(symbol, tf, period_middle, 0, mm, ap);
      int hL=iMA(symbol, tf, period_long,   0, mm, ap);
      if(hS==INVALID_HANDLE || hM==INVALID_HANDLE || hL==INVALID_HANDLE)
      {
         WriteResponseError(id,"iMA handle failed",(int)GetLastError());
         return;
      }

      double bS[], bM[], bL[];
      if(CopyBuffer(hS,0,ma_shift,1,bS)!=1 ||
         CopyBuffer(hM,0,ma_shift,1,bM)!=1 ||
         CopyBuffer(hL,0,ma_shift,1,bL)!=1)
      {
         WriteResponseError(id,"CopyBuffer(iMA) failed",(int)GetLastError());
         return;
      }

      MqlRates r[];
      if(CopyRates(symbol, tf, ma_shift, 1, r)!=1)
      {
         WriteResponseError(id,"CopyRates for MA bar failed",(int)GetLastError());
         return;
      }

      WriteResponseOK_MA_Latest(id, symbol, timeframe_s,
                                period_short, period_middle, period_long,
                                method_norm, price_norm,
                                bS[0], bM[0], bL[0],
                                r[0].time, r[0].close);
      return;
   }
   //--- 全部入りCSV（ローソク＋移動平均＋RSI）
   else if(action=="COPY_MA")
   {
      if(symbol=="")
      {
         WriteResponseError(id,"missing symbol");
         return;
      }

      ENUM_TIMEFRAMES tf;
      if(!StrToTimeframe(timeframe_s, tf))
      {
         WriteResponseError(id,"bad timeframe: "+timeframe_s);
         return;
      }
      ENUM_MA_METHOD mm;
      string         method_norm="";
      if(!StrToMaMethod(method_s, mm, method_norm))
      {
         WriteResponseError(id,"bad method: "+method_s);
         return;
      }
      ENUM_APPLIED_PRICE ap;
      string             price_norm="";
      if(!StrToAppliedPrice(price_s, ap, price_norm))
      {
         WriteResponseError(id,"bad applied_price: "+price_s);
         return;
      }

      if(period_short<=0)  period_short=5;
      if(period_middle<=0) period_middle=20;
      if(period_long<=0)   period_long=60;

      // RSIの期間
      if(period_rsi<=0) period_rsi = 14;

      ResetLastError();
      int bars_total = Bars(symbol, tf);
      int err_bars   = GetLastError();
      if(bars_total <= 0)
      {
         WriteResponseError(id,"Bars() failed",(int)err_bars);
         return;
      }
      if(count <= 0 || count > bars_total)
         count = bars_total;

      int hS   = iMA(symbol, tf, MathMax(1,period_short),  0, mm, ap);
      int hM   = iMA(symbol, tf, MathMax(1,period_middle), 0, mm, ap);
      int hL   = iMA(symbol, tf, MathMax(1,period_long),   0, mm, ap);
      int hRsi = iRSI(symbol, tf, period_rsi, ap);
      if(hS==INVALID_HANDLE || hM==INVALID_HANDLE ||
         hL==INVALID_HANDLE || hRsi==INVALID_HANDLE)
      {
         WriteResponseError(id,"iMA/iRSI handle failed",(int)GetLastError());
         return;
      }

      MqlRates rates[];
      int copied=CopyRates(symbol, tf, 0, count, rates);
      if(copied<=0)
      {
         WriteResponseError(id,"CopyRates failed",(int)GetLastError());
         return;
      }

      double bS[], bM[], bL[], bRsi[];
      if(CopyBuffer(hS,0,0,copied,bS)!=copied ||
         CopyBuffer(hM,0,0,copied,bM)!=copied ||
         CopyBuffer(hL,0,0,copied,bL)!=copied ||
         CopyBuffer(hRsi,0,0,copied,bRsi)!=copied)
      {
         WriteResponseError(id,"CopyBuffer(iMA/iRSI) count mismatch",(int)GetLastError());
         return;
      }

      string csv = WriteBarsFullCsv(id, rates, bS, bM, bL, bRsi, copied);
      if(csv=="")
      {
         WriteResponseError(id,"write full bars csv failed");
         return;
      }

      int resp=FileOpen(RespFileName(id), FILE_WRITE|FILE_COMMON|FILE_ANSI);
      if(resp==INVALID_HANDLE)
      {
         Print("resp(copy_ma/full) open failed id=",id);
         return;
      }
      FileWriteString(resp,"ok=true\r\n");
      FileWriteString(resp,"id="+id+"\r\n");
      FileWriteString(resp,"symbol="+symbol+"\r\n");
      FileWriteString(resp,"timeframe="+timeframe_s+"\r\n");
      FileWriteString(resp,"period_short="+(string)period_short+"\r\n");
      FileWriteString(resp,"period_middle="+(string)period_middle+"\r\n");
      FileWriteString(resp,"period_long="+(string)period_long+"\r\n");
      FileWriteString(resp,"period_rsi="+(string)period_rsi+"\r\n");
      FileWriteString(resp,"method="+method_norm+"\r\n");
      FileWriteString(resp,"applied_price="+price_norm+"\r\n");
      FileWriteString(resp,"count="+(string)copied+"\r\n");
      FileWriteString(resp,"data_file="+csv+"\r\n");
      FileClose(resp);
      return;
   }
   else
   {
      WriteResponseError(id, "unknown action: "+action);
      return;
   }
}
//+------------------------------------------------------------------+
