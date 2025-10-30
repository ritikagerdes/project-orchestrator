import React, { useEffect, useState } from "react";
import api from '../services/axiosConfig';


export default function AdminPanel() {
  const [rates, setRates] = useState({});
  const [editing, setEditing] = useState(false);
  useEffect(() => { fetchRates(); }, []);
  async function fetchRates(){
    const res = await api.get("/api/admin/ratecard");
    setRates(res.data.rates);
  }
  async function save(){
    await api.put("/api/admin/ratecard", {rates});
    setEditing(false);
    fetchRates();
  }
  return (
    <div style={{width:320, border:"1px solid #ccc", padding:12, background:"white"}}>
      <h4>Admin - Rate Card</h4>
      {Object.entries(rates).map(([role,rate]) => (
        <div key={role} style={{display:"flex", justifyContent:"space-between", marginBottom:6}}>
          <div style={{width:"60%"}}>{role}</div>
          <div style={{width:"35%"}}>
            <input value={rate} disabled={!editing} onChange={e => setRates({...rates, [role]: parseFloat(e.target.value) || 0})} style={{width:"100%"}} />
          </div>
        </div>
      ))}
      <div style={{marginTop:8}}>
        {editing ? <><button onClick={save}>Save</button> <button onClick={()=>{setEditing(false); fetchRates();}}>Cancel</button></> : <button onClick={()=>setEditing(true)}>Edit</button>}
      </div>
    </div>
  );
}