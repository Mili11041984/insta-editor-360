import{j as e,B as r,L as l}from"./index-B46R6SbF.js";
import{u as m,P as c,p as x,a as p}from"./mentorship-launch-CphRacMg.js";
import{C as u}from"./crown-DYq5zbnC.js";
import{C as n}from"./check-u-8M5Y4B.js";

const f={
  agency:[
    "Insta Editor 360 Social Growth Platform",
    "Post & reel analytics & insights",
    "AI content assistant & editor",
    "1 device activation · Lifetime access"
  ]
};

function y(){
  return e.jsx("div",{
    className:"mx-auto mt-8 max-w-md",
    children:e.jsxs("div",{
      className:"matrix-card relative flex flex-col rounded-2xl border border-primary/50 bg-card/90 p-8 backdrop-blur shadow-lg matrix-glow text-left",
      children:[
        e.jsxs("span",{
          className:"absolute -top-3 left-6 inline-flex items-center gap-1 rounded-full bg-primary px-3 py-0.5 text-xs font-semibold text-primary-foreground",
          children:[e.jsx(u,{className:"h-3 w-3"}),"Lifetime Access"]
        }),
        e.jsx("h3",{
          className:"font-mono text-base font-semibold uppercase tracking-wider text-foreground",
          children:"Insta Editor 360"
        }),
        e.jsx("p",{className:"text-xs text-muted-foreground",children:"One-time payment · No subscription"}),
        e.jsxs("div",{
          className:"mt-4 flex items-baseline gap-1",
          children:[
            e.jsxs("span",{className:"text-4xl font-bold tracking-tight text-primary",children:["₹1,000"]}),
            e.jsx("span",{className:"text-xs text-muted-foreground",children:"/ lifetime"})
          ]
        }),
        e.jsxs("p",{
          className:"mt-1 text-sm text-muted-foreground",
          children:["or ",e.jsxs("span",{className:"font-medium text-foreground",children:["10 USDT"]})]
        }),
        e.jsx("ul",{
          className:"mt-6 flex-1 space-y-3",
          children:f.agency.map(i=>e.jsxs("li",{
            className:"flex items-start gap-2.5 text-sm",
            children:[
              e.jsx(n,{className:"mt-0.5 h-4 w-4 shrink-0 text-primary"}),
              e.jsx("span",{className:"text-muted-foreground",children:i})
            ]
          },i))
        }),
        e.jsx(r,{
          asChild:!0,
          className:"mt-8 w-full rounded-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-md",
          children:e.jsx(l,{to:"/login",children:"Get Insta Editor 360"})
        })
      ]
    })
  })
}
export{y as P};
