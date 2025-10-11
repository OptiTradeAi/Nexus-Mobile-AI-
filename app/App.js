import React, { useState, useEffect } from 'react';
import { SafeAreaView, Text, View, FlatList } from 'react-native';

export default function App(){
  const [history, setHistory] = useState([]);
  useEffect(()=> {
    // placeholder: later connect to backend history endpoint to fetch signals
  },[]);
  return (
    <SafeAreaView style={{flex:1,padding:12}}>
      <Text style={{fontSize:22,fontWeight:'bold'}}>Nexus AI</Text>
      <View style={{marginTop:12}}>
        <Text>Área do gráfico espelhado (aqui será embutido o player/webview)</Text>
      </View>
      <View style={{marginTop:20}}>
        <Text style={{fontWeight:'bold'}}>Histórico de sinais</Text>
        <FlatList data={history} renderItem={({item}) => <Text>{item.timestamp} — {item.pair} — {item.confidence}</Text>} keyExtractor={(i,idx)=>String(idx)} />
      </View>
    </SafeAreaView>
  );
}
