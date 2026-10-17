import {useRef,useState} from 'react';
import {emptyPracticeStore,parsePracticeStore,PRACTICE_KEY} from './sequencePractice';
import type {PracticeStore} from './sequencePractice';

export function useSequenceNotebook(){
  const [initial]=useState(()=>{
    try{return {data:parsePracticeStore(localStorage.getItem(PRACTICE_KEY)),error:'',readable:true};}
    catch(e){return {data:emptyPracticeStore(),error:`기록 불러오기 실패: ${String(e)}. 이번 기록은 JSON으로 내보내세요.`,readable:false};}
  });
  const [notebook,setNotebook]=useState(initial.data);
  const [storageError,setStorageError]=useState(initial.error);
  const current=useRef(initial.data);
  function updateNotebook(update:(previous:PracticeStore)=>PracticeStore){
    const next=update(current.current);
    current.current=next;
    setNotebook(next);
    if(!initial.readable)return;
    try{localStorage.setItem(PRACTICE_KEY,JSON.stringify(next));setStorageError('');}
    catch(e){setStorageError(`브라우저 저장 실패: ${String(e)}. 현재 탭에는 남아 있습니다. JSON으로 내보내세요.`);}
  }
  return {notebook,updateNotebook,storageError};
}
