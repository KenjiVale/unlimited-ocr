"use client";
import {useEffect,useState} from "react";import {api} from "../../lib/api";import {Nav} from "../../components/nav";
export default function System(){const [data,setData]=useState<any>({});useEffect(()=>{const load=()=>Promise.all(['health','system/gpu','system/model','system/worker','system/storage'].map(x=>api(`/api/${x}`))).then(x=>setData({health:x[0],gpu:x[1],model:x[2],worker:x[3],storage:x[4]}));load();const t=setInterval(load,5000);return()=>clearInterval(t)},[]);return <main><Nav/><h1>System</h1><pre>{JSON.stringify(data,null,2)}</pre></main>}
