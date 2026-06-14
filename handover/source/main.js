
(function(){
  "use strict";
  /* nav scroll state */
  var nav=document.getElementById('nav');
  var onScroll=function(){ if(window.scrollY>24){nav.classList.add('scrolled')}else{nav.classList.remove('scrolled')} };
  onScroll(); window.addEventListener('scroll',onScroll,{passive:true});

  /* mobile menu */
  var menu=document.getElementById('mMenu'),tog=document.getElementById('navToggle'),cls=document.getElementById('navClose');
  var openM=function(){menu.classList.add('open');tog.setAttribute('aria-expanded','true');document.body.style.overflow='hidden'};
  var closeM=function(){menu.classList.remove('open');tog.setAttribute('aria-expanded','false');document.body.style.overflow=''};
  tog.addEventListener('click',openM); cls.addEventListener('click',closeM);
  menu.querySelectorAll('a').forEach(function(a){a.addEventListener('click',closeM)});

  /* faq accordion */
  document.querySelectorAll('.faq-item').forEach(function(item){
    var q=item.querySelector('.faq-q'),a=item.querySelector('.faq-a');
    q.addEventListener('click',function(){
      var open=item.classList.contains('open');
      document.querySelectorAll('.faq-item.open').forEach(function(o){o.classList.remove('open');o.querySelector('.faq-q').setAttribute('aria-expanded','false');o.querySelector('.faq-a').style.maxHeight=null});
      if(!open){item.classList.add('open');q.setAttribute('aria-expanded','true');a.style.maxHeight=a.scrollHeight+'px'}
    });
  });

  /* reveal on scroll */
  var rev=document.querySelectorAll('.reveal');
  if('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.12,rootMargin:'0px 0px -8% 0px'});
    rev.forEach(function(el){io.observe(el)});
  } else { rev.forEach(function(el){el.classList.add('in')}); }

  /* lead form (demo — no backend) */
  var submit=document.getElementById('leadSubmit');
  if(submit){
    submit.addEventListener('click',function(){
      var fn=document.getElementById('fn'),em=document.getElementById('em');
      var ok=true;
      [fn,em].forEach(function(f){ if(!f.value.trim()){f.style.borderColor='var(--clay)';ok=false}else{f.style.borderColor=''} });
      if(em.value && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em.value)){em.style.borderColor='var(--clay)';ok=false}
      if(!ok)return;
      document.querySelector('#leadForm .form-live').style.display='none';
      document.getElementById('formSuccess').classList.add('show');
    });
  }

  /* language toggle (visual only — wire to i18n later) */
  document.querySelectorAll('.lang').forEach(function(group){
    group.querySelectorAll('button').forEach(function(b){
      b.addEventListener('click',function(){
        group.querySelectorAll('button').forEach(function(x){x.classList.remove('on')});
        b.classList.add('on');
      });
    });
  });
})();
