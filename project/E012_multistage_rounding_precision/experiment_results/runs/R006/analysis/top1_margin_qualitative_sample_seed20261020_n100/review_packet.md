# 低 Margin Top1 翻转：100 例独立评阅包

从 876 个参考 Logit Margin < 0.05 的翻转位置中，以种子 20261020 等概率、无放回抽样 100 例；涉及 93 篇文档。顺序为抽样返回顺序，未按候选内容筛选。

每例前缀包含预测位置本身：位置 t 的 logits 预测下一 token，输入前缀严格为 input_ids[:t+1]。下方展示末 64 个输入 token 解码文本。

单 token 用 Python repr 显示空格和换行；候选后缀由末 12 个输入 token 与该候选联合解码，只追加一个 token。BPE 片段可能是半个词，不能当完整续写。完整前缀和字节信息见 samples.jsonl。

参考版本是数值对照，不能据名称视为语义金标。此包不展示原文实际下一 token；该辅助信息仅单列存于 samples 文件，超过已保存输入的范围记为 null。数据准备阶段未加主观标签。

| 域 | 样本数 | 独立文档数 |
|---|---:|---:|
| news | 13 | 11 |
| reviews | 33 | 32 |
| web | 54 | 50 |

## S001

文档 `imdb_test:2857`；域 reviews；位置 91（从 0 开始）；参考 Logit Margin 0.004509925842。

输入前缀末 64 token：

```text
 down to her undies, pours tomato juice on her body so her boyfriend can lick it off, performs a seductive dance, then goes off to kill the policemen who killed the ninja she's possessed by. Only to be hunted down by a one-eyed ninja master. Just like in real life, eh? Enl
```

参考版本候选：ID 2192；单 token repr：

```text
'ai'
```

末 12 输入 token + 该候选联合解码：

```text
 master. Just like in real life, eh? Enlai
```

当前版本候选：ID 2116；单 token repr：

```text
'iven'
```

末 12 输入 token + 该候选联合解码：

```text
 master. Just like in real life, eh? Enliven
```


## S002

文档 `c4_official_validation_first10000:7411`；域 web；位置 73（从 0 开始）；参考 Logit Margin 0.01982688904。

输入前缀末 64 token：

```text
 of the event; Varsity team won first place in Illinois State Science Olympiad held April 10 a the University of Illinois at Urbana-Champaign. They will compete in the nationals May 22. Students mentioned include Leah Rivkin, Sean Ye, Elizabeth Lee, Vivian Jou, Michael Gobeli, Shannon
```

参考版本候选：ID 12336；单 token repr：

```text
' Lee'
```

末 12 输入 token + 该候选联合解码：

```text
 Lee, Vivian Jou, Michael Gobeli, Shannon Lee
```

当前版本候选：ID 507；单 token repr：

```text
' O'
```

末 12 输入 token + 该候选联合解码：

```text
 Lee, Vivian Jou, Michael Gobeli, Shannon O
```


## S003

文档 `imdb_test:21847`；域 reviews；位置 23（从 0 开始）；参考 Logit Margin 0.009262084961。

输入前缀末 64 token：

```text
<|begin_of_text|>I saw this film at a special screening. At first I thought the movie would be like a typical Amanda Bynes
```

参考版本候选：ID 23160；单 token repr：

```text
' comedy'
```

末 12 输入 token + 该候选联合解码：

```text
 I thought the movie would be like a typical Amanda Bynes comedy
```

当前版本候选：ID 4632；单 token repr：

```text
' film'
```

末 12 输入 token + 该候选联合解码：

```text
 I thought the movie would be like a typical Amanda Bynes film
```


## S004

文档 `imdb_test:14873`；域 reviews；位置 16（从 0 开始）；参考 Logit Margin 0.01740264893。

输入前缀末 64 token：

```text
<|begin_of_text|>Two hard-luck but crafty ladies decide to act like HAVANA W
```

参考版本候选：ID 1750；单 token repr：

```text
'IL'
```

末 12 输入 token + 该候选联合解码：

```text
 but crafty ladies decide to act like HAVANA WIL
```

当前版本候选：ID 37550；单 token repr：

```text
'ALK'
```

末 12 输入 token + 该候选联合解码：

```text
 but crafty ladies decide to act like HAVANA WALK
```


## S005

文档 `imdb_test:6700`；域 reviews；位置 52（从 0 开始）；参考 Logit Margin 0.01656913757。

输入前缀末 64 token：

```text
<|begin_of_text|>When you watch a Seagal movie, you expect good action. You expect fighting, not just a lot of shooting like in this flick. And: you expect a rather simple story. OK, I can live with a more complex story even though it's a
```

参考版本候选：ID 2766；单 token repr：

```text
' bit'
```

末 12 输入 token + 该候选联合解码：

```text
 can live with a more complex story even though it's a bit
```

当前版本候选：ID 1369；单 token repr：

```text
' Se'
```

末 12 输入 token + 该候选联合解码：

```text
 can live with a more complex story even though it's a Se
```


## S006

文档 `c4_official_validation_first10000:4647`；域 web；位置 26（从 0 开始）；参考 Logit Margin 0.001748085022。

输入前缀末 64 token：

```text
<|begin_of_text|>There's no one way to show riders the way, but some are better than others.
The blog Greater Greater Washington reports that the
```

参考版本候选：ID 11182；单 token repr：

```text
' District'
```

末 12 输入 token + 该候选联合解码：

```text
 better than others.
The blog Greater Greater Washington reports that the District
```

当前版本候选：ID 11162；单 token repr：

```text
' DC'
```

末 12 输入 token + 该候选联合解码：

```text
 better than others.
The blog Greater Greater Washington reports that the DC
```


## S007

文档 `c4_official_validation_first10000:2730`；域 web；位置 88（从 0 开始）；参考 Logit Margin 0.02085781097。

输入前缀末 64 token：

```text
ani, Vice President of Marketing & Sales for L3 MAPPS Power Systems and Simulation. "Our simulation technology is already employed at six EDF Energy facilities and will soon be added to the Nuclear Power Academy in Barnwood, Gloucester."
"EDF Energy is happy to work with L3 MAPPS to add two
```

参考版本候选：ID 5217；单 token repr：

```text
' additional'
```

末 12 输入 token + 该候选联合解码：

```text
 is happy to work with L3 MAPPS to add two additional
```

当前版本候选：ID 502；单 token repr：

```text
' new'
```

末 12 输入 token + 该候选联合解码：

```text
 is happy to work with L3 MAPPS to add two new
```


## S008

文档 `c4_official_validation_first10000:7922`；域 web；位置 51（从 0 开始）；参考 Logit Margin 0.0214214325。

输入前缀末 64 token：

```text
<|begin_of_text|>Hello everybody!! . Let’s do some fun with your friend’s pc by disabling his pc mouse. It’s a very simple but dangerous method. By this technique anybody can be freaked out. Don’t do ever this with your own PC. You may
```

参考版本候选：ID 387；单 token repr：

```text
' be'
```

末 12 输入 token + 该候选联合解码：

```text
 Don’t do ever this with your own PC. You may be
```

当前版本候选：ID 636；单 token repr：

```text
' get'
```

末 12 输入 token + 该候选联合解码：

```text
 Don’t do ever this with your own PC. You may get
```


## S009

文档 `ag_news_test:5471`；域 news；位置 20（从 0 开始）；参考 Logit Margin 0.02310371399。

输入前缀末 64 token：

```text
<|begin_of_text|>Refugees #39; hopes for return will outlive Arafat BEIRUT, Lebanon
```

参考版本候选：ID 482；单 token repr：

```text
' -'
```

末 12 输入 token + 该候选联合解码：

```text
 return will outlive Arafat BEIRUT, Lebanon -
```

当前版本候选：ID 1198；单 token repr：

```text
' --'
```

末 12 输入 token + 该候选联合解码：

```text
 return will outlive Arafat BEIRUT, Lebanon --
```


## S010

文档 `imdb_test:14846`；域 reviews；位置 57（从 0 开始）；参考 Logit Margin 0.01780319214。

输入前缀末 64 token：

```text
<|begin_of_text|>I was at a friends house for Thanksgiving and watched a DVD of the movie, Eddie Monroe. I've been a fan of Indie Films for almost 20 years, (I loved the Brothers McMullen), and was impressed how good this movie is. My friend, who works at Mag
```

参考版本候选：ID 52750；单 token repr：

```text
'uire'
```

末 12 输入 token + 该候选联合解码：

```text
 good this movie is. My friend, who works at Maguire
```

当前版本候选：ID 307；单 token repr：

```text
'id'
```

末 12 输入 token + 该候选联合解码：

```text
 good this movie is. My friend, who works at Magid
```


## S011

文档 `imdb_test:4695`；域 reviews；位置 33（从 0 开始）；参考 Logit Margin 0.01091003418。

输入前缀末 64 token：

```text
<|begin_of_text|>Cameron Mitchell plays an actor who is dating a young actress who used to date the head of a movie studio (she's too young for both of them!). At
```

参考版本候选：ID 279；单 token repr：

```text
' the'
```

末 12 输入 token + 该候选联合解码：

```text
 studio (she's too young for both of them!). At the
```

当前版本候选：ID 1176；单 token repr：

```text
' first'
```

末 12 输入 token + 该候选联合解码：

```text
 studio (she's too young for both of them!). At first
```


## S012

文档 `c4_official_validation_first10000:8386`；域 web；位置 100（从 0 开始）；参考 Logit Margin 0.04208374023。

输入前缀末 64 token：

```text
 may actually be causing additional harm or prolonged suffering. One of the most common treatment methods, the prescribing of opioid medications such as Vicodin and OxyContin, can have undesirable side effects and lead to addiction. In his book CONQUER CHRONIC PAIN: An Innovative Mind-Body Approach (Hazelden
```

参考版本候选：ID 8245；单 token repr：

```text
' Information'
```

末 12 输入 token + 该候选联合解码：

```text
 PAIN: An Innovative Mind-Body Approach (Hazelden Information
```

当前版本候选：ID 11；单 token repr：

```text
','
```

末 12 输入 token + 该候选联合解码：

```text
 PAIN: An Innovative Mind-Body Approach (Hazelden,
```


## S013

文档 `ag_news_test:6989`；域 news；位置 53（从 0 开始）；参考 Logit Margin 0.003542900085。

输入前缀末 64 token：

```text
<|begin_of_text|>Industrials lift stocks THE stock market opened higher today as industrials stocks mitigated the effects of a weaker resources sector.  quot;Commodity prices are generally weaker on renewed speculation of weaker demand in China, quot; Wilson HTM senior client adviser Angus
```

参考版本候选：ID 30524；单 token repr：

```text
' Campbell'
```

末 12 输入 token + 该候选联合解码：

```text
 in China, quot; Wilson HTM senior client adviser Angus Campbell
```

当前版本候选：ID 8444；单 token repr：

```text
' Gl'
```

末 12 输入 token + 该候选联合解码：

```text
 in China, quot; Wilson HTM senior client adviser Angus Gl
```


## S014

文档 `c4_official_validation_first10000:1660`；域 web；位置 80（从 0 开始）；参考 Logit Margin 0.03095817566。

输入前缀末 64 token：

```text
 the dreams of women entrepreneurs a reality is wegg®’s purpose. We are here for you.
Two young entrepreneurs in 1987 set out to find quality driven luggage for women. When their search didn’t pan out, Barbara Bradley Baekgaard and Patricia Miller (pictured L-R) decided to make their own
```

参考版本候选：ID 51597；单 token repr：

```text
' luggage'
```

末 12 输入 token + 该候选联合解码：

```text
 Patricia Miller (pictured L-R) decided to make their own luggage
```

当前版本候选：ID 13；单 token repr：

```text
'.'
```

末 12 输入 token + 该候选联合解码：

```text
 Patricia Miller (pictured L-R) decided to make their own.
```


## S015

文档 `ag_news_test:3`；域 news；位置 18（从 0 开始）；参考 Logit Margin 0.0460062027。

输入前缀末 64 token：

```text
<|begin_of_text|>Prediction Unit Helps Forecast Wildfires (AP) AP - It's barely dawn when Mike Fitz
```

参考版本候选：ID 15124；单 token repr：

```text
'sim'
```

末 12 输入 token + 该候选联合解码：

```text
 (AP) AP - It's barely dawn when Mike Fitzsim
```

当前版本候选：ID 71；单 token repr：

```text
'h'
```

末 12 输入 token + 该候选联合解码：

```text
 (AP) AP - It's barely dawn when Mike Fitzh
```


## S016

文档 `c4_official_validation_first10000:4849`；域 web；位置 55（从 0 开始）；参考 Logit Margin 0.04088020325。

输入前缀末 64 token：

```text
<|begin_of_text|>Includes phone and battery only. No cables or sim card included. Cellular service locked to MetroPCS. Clean ESN, ZTE BAR style smartphone in Midnight. Phone glass cracked/shattered/chipped, housing scuffed/scratched/dented/dinged. Phone is used and
```

参考版本候选：ID 706；单 token repr：

```text
' has'
```

末 12 输入 token + 该候选联合解码：

```text
/scratched/dented/dinged. Phone is used and has
```

当前版本候选：ID 304；单 token repr：

```text
' in'
```

末 12 输入 token + 该候选联合解码：

```text
/scratched/dented/dinged. Phone is used and in
```


## S017

文档 `c4_official_validation_first10000:859`；域 web；位置 32（从 0 开始）；参考 Logit Margin 0.02502536774。

输入前缀末 64 token：

```text
<|begin_of_text|>Science Communication… I think that is something we all hope we are doing, communicating the science with our clientele. Today I came across this article that has paired the
```

参考版本候选：ID 8198；单 token repr：

```text
' science'
```

末 12 输入 token + 该候选联合解码：

```text
 clientele. Today I came across this article that has paired the science
```

当前版本候选：ID 1403；单 token repr：

```text
' two'
```

末 12 输入 token + 该候选联合解码：

```text
 clientele. Today I came across this article that has paired the two
```


## S018

文档 `c4_official_validation_first10000:2501`；域 web；位置 124（从 0 开始）；参考 Logit Margin 0.02068138123。

输入前缀末 64 token：

```text
 EtG alcohol urine test is what is primarily used.
These tests look for the compound Ethyl Glucuronide, shortened to EtG in most instances. This compound is a metabolite of alcohol and is present in the body after one consumes a drink. However, this alcohol urine test is only accurate for roughly the
```

参考版本候选：ID 3347；单 token repr：

```text
' past'
```

末 12 输入 token + 该候选联合解码：

```text
 However, this alcohol urine test is only accurate for roughly the past
```

当前版本候选：ID 1566；单 token repr：

```text
' last'
```

末 12 输入 token + 该候选联合解码：

```text
 However, this alcohol urine test is only accurate for roughly the last
```


## S019

文档 `ag_news_test:5993`；域 news；位置 18（从 0 开始）；参考 Logit Margin 0.007776260376。

输入前缀末 64 token：

```text
<|begin_of_text|>Putin backs veto for members of expanded Security Council Russian President Vladimir Putin yesterday rejected a key recommendation
```

参考版本候选：ID 315；单 token repr：

```text
' of'
```

末 12 输入 token + 该候选联合解码：

```text
 expanded Security Council Russian President Vladimir Putin yesterday rejected a key recommendation of
```

当前版本候选：ID 505；单 token repr：

```text
' from'
```

末 12 输入 token + 该候选联合解码：

```text
 expanded Security Council Russian President Vladimir Putin yesterday rejected a key recommendation from
```


## S020

文档 `c4_official_validation_first10000:3208`；域 web；位置 94（从 0 开始）；参考 Logit Margin 0.0007190704346。

输入前缀末 64 token：

```text
) to go with 4 assists for the Kings, while Marvin Bagley III tallied 22 points and 12 rebounds. Willie Cauley-Stein also recorded a career-high 18 rebounds in the game. Justin Jackson led the Mavericks with 19 points (9-16 FG) to go with 
```

参考版本候选：ID 19；单 token repr：

```text
'4'
```

末 12 输入 token + 该候选联合解码：

```text
19 points (9-16 FG) to go with 4
```

当前版本候选：ID 20；单 token repr：

```text
'5'
```

末 12 输入 token + 该候选联合解码：

```text
19 points (9-16 FG) to go with 5
```


## S021

文档 `c4_official_validation_first10000:6747`；域 web；位置 22（从 0 开始）；参考 Logit Margin 0.01046466827。

输入前缀末 64 token：

```text
<|begin_of_text|>indigoOne blog: Does ‘junk mail’ still work?
“Junk Mail’ or DM blast
```

参考版本候选：ID 5380；单 token repr：

```text
'?\n'
```

末 12 输入 token + 该候选联合解码：

```text
’ still work?
“Junk Mail’ or DM blast?

```

当前版本候选：ID 374；单 token repr：

```text
' is'
```

末 12 输入 token + 该候选联合解码：

```text
’ still work?
“Junk Mail’ or DM blast is
```


## S022

文档 `ag_news_test:878`；域 news；位置 40（从 0 开始）；参考 Logit Margin 0.04613018036。

输入前缀末 64 token：

```text
<|begin_of_text|>Women #39;s basketball team finds special place in Chancellor #39;s heart The medal ceremony had ended. Van Chancellor had already shed a few tears, but he had held his emotions together through all the
```

参考版本候选：ID 3953；单 token repr：

```text
' games'
```

末 12 输入 token + 该候选联合解码：

```text
 tears, but he had held his emotions together through all the games
```

当前版本候选：ID 80342；单 token repr：

```text
' hugs'
```

末 12 输入 token + 该候选联合解码：

```text
 tears, but he had held his emotions together through all the hugs
```


## S023

文档 `c4_official_validation_first10000:9226`；域 web；位置 15（从 0 开始）；参考 Logit Margin 0.02260494232。

输入前缀末 64 token：

```text
<|begin_of_text|>We are moving forward with our MVP development, and it’s time for another
```

参考版本候选：ID 20140；单 token repr：

```text
' iteration'
```

末 12 输入 token + 该候选联合解码：

```text
 forward with our MVP development, and it’s time for another iteration
```

当前版本候选：ID 2713；单 token repr：

```text
' update'
```

末 12 输入 token + 该候选联合解码：

```text
 forward with our MVP development, and it’s time for another update
```


## S024

文档 `c4_official_validation_first10000:279`；域 web；位置 112（从 0 开始）；参考 Logit Margin 0.02194976807。

输入前缀末 64 token：

```text
He linked to the video on Twitter, captioning it with two hearts and two baby emojis.
Teigen also posted a self-portrait on Snapchat of her protruding stomach in a fitted black dress. “Very excited to not have to hide this anymore,” she wrote.
Teigen, 31, and Legend, 
```

参考版本候选：ID 1987；单 token repr：

```text
'38'
```

末 12 输入 token + 该候选联合解码：

```text
 wrote.
Teigen, 31, and Legend, 38
```

当前版本候选：ID 2137；单 token repr：

```text
'39'
```

末 12 输入 token + 该候选联合解码：

```text
 wrote.
Teigen, 31, and Legend, 39
```


## S025

文档 `imdb_test:13554`；域 reviews；位置 60（从 0 开始）；参考 Logit Margin 0.001418113708。

输入前缀末 64 token：

```text
<|begin_of_text|>Another of the endless amount of cookie-cutter 'Kickboxers Fight to the Death for the Amusement of Wealthy Scumbags' films that there were so many of in the 90s... Y'know, the ones created by taking the words 'Death', 'Blood' and '
```

参考版本候选：ID 37；单 token repr：

```text
'F'
```

末 12 输入 token + 该候选联合解码：

```text
 by taking the words 'Death', 'Blood' and 'F
```

当前版本候选：ID 66754；单 token repr：

```text
'Fight'
```

末 12 输入 token + 该候选联合解码：

```text
 by taking the words 'Death', 'Blood' and 'Fight
```


## S026

文档 `imdb_test:15984`；域 reviews；位置 93（从 0 开始）；参考 Logit Margin 0.02788162231。

输入前缀末 64 token：

```text
 is my all time favourite sitcom, It ain't half hot Mum is also a classic as is You Rang M'Lord. I don't regard Hi De Hi as a classic, but it is still funny.<br /><br />It's about a holiday camp, similar to Butlins, but instead of red
```

参考版本候选：ID 56737；单 token repr：

```text
' coats'
```

末 12 输入 token + 该候选联合解码：

```text
 camp, similar to Butlins, but instead of red coats
```

当前版本候选：ID 1030；单 token repr：

```text
'co'
```

末 12 输入 token + 该候选联合解码：

```text
 camp, similar to Butlins, but instead of redco
```


## S027

文档 `c4_official_validation_first10000:8953`；域 web；位置 79（从 0 开始）；参考 Logit Margin 0.006078720093。

输入前缀末 64 token：

```text
 the small child, and the smiling faces. Smell the rain, and feel the wind. Live your life to the fullest potential.
My motto in life has always been to try and pay attention to details no matter what — those small things that make life worth living. Why?
These days, our lives have become so
```

参考版本候选：ID 13326；单 token repr：

```text
' busy'
```

末 12 输入 token + 该候选联合解码：

```text
 living. Why?
These days, our lives have become so busy
```

当前版本候选：ID 5043；单 token repr：

```text
' fast'
```

末 12 输入 token + 该候选联合解码：

```text
 living. Why?
These days, our lives have become so fast
```


## S028

文档 `c4_official_validation_first10000:2730`；域 web；位置 96（从 0 开始）；参考 Logit Margin 0.00501537323。

输入前缀末 64 token：

```text
 for L3 MAPPS Power Systems and Simulation. "Our simulation technology is already employed at six EDF Energy facilities and will soon be added to the Nuclear Power Academy in Barnwood, Gloucester."
"EDF Energy is happy to work with L3 MAPPS to add two more simulators to our fleet," said
```

参考版本候选：ID 6941；单 token repr：

```text
' David'
```

末 12 输入 token + 该候选联合解码：

```text
PS to add two more simulators to our fleet," said David
```

当前版本候选：ID 4488；单 token repr：

```text
' Mark'
```

末 12 输入 token + 该候选联合解码：

```text
PS to add two more simulators to our fleet," said Mark
```


## S029

文档 `c4_official_validation_first10000:1715`；域 web；位置 31（从 0 开始）；参考 Logit Margin 0.03616142273。

输入前缀末 64 token：

```text
<|begin_of_text|>Navigator API is good for clients (module writers) that want to show some structure or outline of their document in dedicated window, allowing end user fast navigation and
```

参考版本候选：ID 2680；单 token repr：

```text
' access'
```

末 12 输入 token + 该候选联合解码：

```text
 their document in dedicated window, allowing end user fast navigation and access
```

当前版本候选：ID 24131；单 token repr：

```text
' overview'
```

末 12 输入 token + 该候选联合解码：

```text
 their document in dedicated window, allowing end user fast navigation and overview
```


## S030

文档 `ag_news_test:4284`；域 news；位置 46（从 0 开始）；参考 Logit Margin 0.01745414734。

输入前缀末 64 token：

```text
<|begin_of_text|>Software giant Microsoft rings up multibillion dollar profit gain REDMOND, Washington, Oct 21 (AFP) - The world #39;s biggest software company, Microsoft Corp, said Thursday that its first quarter profits swelled to
```

参考版本候选：ID 400；单 token repr：

```text
' $'
```

末 12 输入 token + 该候选联合解码：

```text
 Corp, said Thursday that its first quarter profits swelled to $
```

当前版本候选：ID 264；单 token repr：

```text
' a'
```

末 12 输入 token + 该候选联合解码：

```text
 Corp, said Thursday that its first quarter profits swelled to a
```


## S031

文档 `ag_news_test:3335`；域 news；位置 1（从 0 开始）；参考 Logit Margin 0.01107883453。

输入前缀末 64 token：

```text
<|begin_of_text|>Anal
```

参考版本候选：ID 99335；单 token repr：

```text
'ysts'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Analysts
```

当前版本候选：ID 599；单 token repr：

```text
'yst'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Analyst
```


## S032

文档 `c4_official_validation_first10000:1737`；域 web；位置 115（从 0 开始）；参考 Logit Margin 0.03314590454。

输入前缀末 64 token：

```text
 like her career making classic Hallyu sageuk Dae Jang Geum has achieved untouchable levels of worldwide success during it’s airing era. I do wonder how the ratings of Saimdang will start off, and will it be interest in the drama or in her comeback after a thirteen year hiatus after
```

参考版本候选：ID 279；单 token repr：

```text
' the'
```

末 12 输入 token + 该候选联合解码：

```text
 the drama or in her comeback after a thirteen year hiatus after the
```

当前版本候选：ID 622；单 token repr：

```text
' J'
```

末 12 输入 token + 该候选联合解码：

```text
 the drama or in her comeback after a thirteen year hiatus after J
```


## S033

文档 `c4_official_validation_first10000:1177`；域 web；位置 88（从 0 开始）；参考 Logit Margin 0.03277778625。

输入前缀末 64 token：

```text
Banking services” tab in our mobile banking app, or the “Online applications” tab in Internet Banking Solutions. You can also call us at 1-888-622-2783.
Check the expiry date and credit limit of your credit card, as well as the withdrawal limits on your Client Card.
Use the
```

参考版本候选：ID 6505；单 token repr：

```text
' mobile'
```

末 12 输入 token + 该候选联合解码：

```text
 well as the withdrawal limits on your Client Card.
Use the mobile
```

当前版本候选：ID 1054；单 token repr：

```text
' “'
```

末 12 输入 token + 该候选联合解码：

```text
 well as the withdrawal limits on your Client Card.
Use the “
```


## S034

文档 `imdb_test:21818`；域 reviews；位置 101（从 0 开始）；参考 Logit Margin 0.01949119568。

输入前缀末 64 token：

```text
 of us who have ever ventured into any part of show business, be it film, music, or writing. I think the film makers could have done a better job with foreshadowing the events that led up to this film becoming a documentary, perhaps by use of a narrator; other than that, the film comes
```

参考版本候选：ID 1022；单 token repr：

```text
' off'
```

末 12 输入 token + 该候选联合解码：

```text
 use of a narrator; other than that, the film comes off
```

当前版本候选：ID 4028；单 token repr：

```text
' across'
```

末 12 输入 token + 该候选联合解码：

```text
 use of a narrator; other than that, the film comes across
```


## S035

文档 `imdb_test:22795`；域 reviews；位置 21（从 0 开始）；参考 Logit Margin 0.02586364746。

输入前缀末 64 token：

```text
<|begin_of_text|>The true story of Phoolan Devi who became a national hero in India because she fought for her
```

参考版本候选：ID 3268；单 token repr：

```text
' rights'
```

末 12 输入 token + 该候选联合解码：

```text
 who became a national hero in India because she fought for her rights
```

当前版本候选：ID 1274；单 token repr：

```text
' people'
```

末 12 输入 token + 该候选联合解码：

```text
 who became a national hero in India because she fought for her people
```


## S036

文档 `c4_official_validation_first10000:3667`；域 web；位置 112（从 0 开始）；参考 Logit Margin 0.0016040802。

输入前缀末 64 token：

```text
 Azure 2, and Samurai Warriors: Sanada Maru. Toukiden 2 released over in Japan on July 28th, and is currently available for PS3, PS4 and PS Vita.
Western fans looking forward to the popular demon hunting RPG game, Toukiden, will find that the second installment
```

参考版本候选：ID 690；单 token repr：

```text
' will'
```

末 12 输入 token + 该候选联合解码：

```text
 game, Toukiden, will find that the second installment will
```

当前版本候选：ID 315；单 token repr：

```text
' of'
```

末 12 输入 token + 该候选联合解码：

```text
 game, Toukiden, will find that the second installment of
```


## S037

文档 `c4_official_validation_first10000:7769`；域 web；位置 99（从 0 开始）；参考 Logit Margin 0.002923965454。

输入前缀末 64 token：

```text
ecanadianencyclopedia.ca/en/article/treaties-1-and-2. Accessed 24 April 2019.
Treaties 1 and 2 were the first of 11 Numbered Treaties negotiated between 1871 and 1921 Treaty 1 was signed 3 August 1871
```

参考版本候选：ID 11；单 token repr：

```text
','
```

末 12 输入 token + 该候选联合解码：

```text
1 Treaty 1 was signed 3 August 1871,
```

当前版本候选：ID 520；单 token repr：

```text
' at'
```

末 12 输入 token + 该候选联合解码：

```text
1 Treaty 1 was signed 3 August 1871 at
```


## S038

文档 `c4_official_validation_first10000:6259`；域 web；位置 11（从 0 开始）；参考 Logit Margin 0.01745414734。

输入前缀末 64 token：

```text
<|begin_of_text|>If you said ‘YES‘ to any of these,
```

参考版本候选：ID 499；单 token repr：

```text
' you'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>If you said ‘YES‘ to any of these, you
```

当前版本候选：ID 1243；单 token repr：

```text
' then'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>If you said ‘YES‘ to any of these, then
```


## S039

文档 `c4_official_validation_first10000:3825`；域 web；位置 35（从 0 开始）；参考 Logit Margin 0.005581855774。

输入前缀末 64 token：

```text
<|begin_of_text|>This was one of my biggest scripts back in the days.
I sold hundreds of copies of this script, before a series of events led me to completely lose the script, the
```

参考版本候选：ID 2592；单 token repr：

```text
' source'
```

末 12 输入 token + 该候选联合解码：

```text
 series of events led me to completely lose the script, the source
```

当前版本候选：ID 6763；单 token repr：

```text
' sales'
```

末 12 输入 token + 该候选联合解码：

```text
 series of events led me to completely lose the script, the sales
```


## S040

文档 `imdb_test:310`；域 reviews；位置 58（从 0 开始）；参考 Logit Margin 0.01470088959。

输入前缀末 64 token：

```text
<|begin_of_text|>I've always loved horror flicks. From some of the usual well-known like "The Exorcist" to some of the more underrated like "Black Christmas" or "Just Before Dawn". But who are people kidding,even calling this trash a b-movie. It's straight up
```

参考版本候选：ID 26964；单 token repr：

```text
' garbage'
```

末 12 输入 token + 该候选联合解码：

```text
 calling this trash a b-movie. It's straight up garbage
```

当前版本候选：ID 23701；单 token repr：

```text
' trash'
```

末 12 输入 token + 该候选联合解码：

```text
 calling this trash a b-movie. It's straight up trash
```


## S041

文档 `imdb_test:423`；域 reviews；位置 34（从 0 开始）；参考 Logit Margin 0.02610588074。

输入前缀末 64 token：

```text
<|begin_of_text|>Man with the Screaming Brain is a story of greed, betrayal and revenge in the a small Bulgarian town. William Cole, wealthy industrialist, winds up with part of
```

参考版本候选：ID 279；单 token repr：

```text
' the'
```

末 12 输入 token + 该候选联合解码：

```text
 William Cole, wealthy industrialist, winds up with part of the
```

当前版本候选：ID 813；单 token repr：

```text
' his'
```

末 12 输入 token + 该候选联合解码：

```text
 William Cole, wealthy industrialist, winds up with part of his
```


## S042

文档 `c4_official_validation_first10000:2585`；域 web；位置 119（从 0 开始）；参考 Logit Margin 0.03529644012。

输入前缀末 64 token：

```text
 lot on their website.
Now I happen to understand what the middle class civil servants on €50k+ per year didn't when they thought up what they thought was a very clever idea and called it a PRSA. This incidentally, is virtually identical to a stakeholder pension in the UK. Anyway, my unique
```

参考版本候选：ID 28781；单 token repr：

```text
' pension'
```

末 12 输入 token + 该候选联合解码：

```text
 a stakeholder pension in the UK. Anyway, my unique pension
```

当前版本候选：ID 323；单 token repr：

```text
' and'
```

末 12 输入 token + 该候选联合解码：

```text
 a stakeholder pension in the UK. Anyway, my unique and
```


## S043

文档 `imdb_test:3159`；域 reviews；位置 26（从 0 开始）；参考 Logit Margin 0.004583358765。

输入前缀末 64 token：

```text
<|begin_of_text|>The story overall, though quite graphic, is actually decent and reasonably interesting to readers. However, the movie was absolutely dreadful. The
```

参考版本候选：ID 15718；单 token repr：

```text
' acting'
```

末 12 输入 token + 该候选联合解码：

```text
 to readers. However, the movie was absolutely dreadful. The acting
```

当前版本候选：ID 4632；单 token repr：

```text
' film'
```

末 12 输入 token + 该候选联合解码：

```text
 to readers. However, the movie was absolutely dreadful. The film
```


## S044

文档 `imdb_test:16892`；域 reviews；位置 97（从 0 开始）；参考 Logit Margin 0.007583618164。

输入前缀末 64 token：

```text
 film builds slowly, but perfectly, and what starts out as a seemingly lost fortysomething's identity crisis unfolds into a beautiful tale with much deeper meaning with regard to the importance of love, loss, family and perhaps more importantly, our life's work.<br /><br />I had never heard of Louis Kahn prior to
```

参考版本候选：ID 420；单 token repr：

```text
' this'
```

末 12 输入 token + 该候选联合解码：

```text
 /><br />I had never heard of Louis Kahn prior to this
```

当前版本候选：ID 10307；单 token repr：

```text
' watching'
```

末 12 输入 token + 该候选联合解码：

```text
 /><br />I had never heard of Louis Kahn prior to watching
```


## S045

文档 `c4_official_validation_first10000:7091`；域 web；位置 18（从 0 开始）；参考 Logit Margin 0.006735801697。

输入前缀末 64 token：

```text
<|begin_of_text|>Morning walk around our shore stopping at ‘The Dairy’ to browse the textiles and ceramics.
```

参考版本候选：ID 1226；单 token repr：

```text
' We'
```

末 12 输入 token + 该候选联合解码：

```text
 at ‘The Dairy’ to browse the textiles and ceramics. We
```

当前版本候选：ID 578；单 token repr：

```text
' The'
```

末 12 输入 token + 该候选联合解码：

```text
 at ‘The Dairy’ to browse the textiles and ceramics. The
```


## S046

文档 `imdb_test:19639`；域 reviews；位置 34（从 0 开始）；参考 Logit Margin 0.04360866547。

输入前缀末 64 token：

```text
<|begin_of_text|>Some people have the ability to use only 3 neurons, one for eating, one for breathing and the other one for s**ting... This is not a movie for
```

参考版本候选：ID 5127；单 token repr：

```text
' everyone'
```

末 12 输入 token + 该候选联合解码：

```text
 one for s**ting... This is not a movie for everyone
```

当前版本候选：ID 279；单 token repr：

```text
' the'
```

末 12 输入 token + 该候选联合解码：

```text
 one for s**ting... This is not a movie for the
```


## S047

文档 `imdb_test:21062`；域 reviews；位置 24（从 0 开始）；参考 Logit Margin 0.00843334198。

输入前缀末 64 token：

```text
<|begin_of_text|>Christine Lahti (Sandy Dunlap) and Mary Tyler Moore (Holly Davis) worked well with soapish
```

参考版本候选：ID 5429；单 token repr：

```text
' script'
```

末 12 输入 token + 该候选联合解码：

```text
 Tyler Moore (Holly Davis) worked well with soapish script
```

当前版本候选：ID 28485；单 token repr：

```text
' humor'
```

末 12 输入 token + 该候选联合解码：

```text
 Tyler Moore (Holly Davis) worked well with soapish humor
```


## S048

文档 `imdb_test:7638`；域 reviews；位置 53（从 0 开始）；参考 Logit Margin 0.01014328003。

输入前缀末 64 token：

```text
<|begin_of_text|>Strange things happen to Americans Will (Greg Evigan), Maura (Alexandra Paul) and their young daughter Aubrey (Briana Evigan, Greg's real life daughter) when they move into a large, newly inherited house in Ireland. Crusty corpses
```

参考版本候选：ID 5101；单 token repr：

```text
' appear'
```

末 12 输入 token + 该候选联合解码：

```text
 a large, newly inherited house in Ireland. Crusty corpses appear
```

当前版本候选：ID 11；单 token repr：

```text
','
```

末 12 输入 token + 该候选联合解码：

```text
 a large, newly inherited house in Ireland. Crusty corpses,
```


## S049

文档 `c4_official_validation_first10000:4806`；域 web；位置 88（从 0 开始）；参考 Logit Margin 0.009071350098。

输入前缀末 64 token：

```text
 Guide  – Now Only $49.97!
DIY 3D Solar Panels Made Easy!
Get YOUR DIY 3D Solar Panels Guide for only $49.97 today! This is an eBook download in PDF format with digital step-by-step video tutorials so there’s no way to mess this up.
It’s
```

参考版本候选：ID 892；单 token repr：

```text
' time'
```

末 12 输入 token + 该候选联合解码：

```text
 so there’s no way to mess this up.
It’s time
```

当前版本候选：ID 4228；单 token repr：

```text
' easy'
```

末 12 输入 token + 该候选联合解码：

```text
 so there’s no way to mess this up.
It’s easy
```


## S050

文档 `imdb_test:4695`；域 reviews；位置 68（从 0 开始）；参考 Logit Margin 0.00386428833。

输入前缀末 64 token：

```text
 an actor who is dating a young actress who used to date the head of a movie studio (she's too young for both of them!). At a party, when he's lighting his cigarette, the studio boss throws a high alcohol content drink in his face, and he catches fire. In the hospital, his face is
```

参考版本候选：ID 25587；单 token repr：

```text
' badly'
```

末 12 输入 token + 该候选联合解码：

```text
 and he catches fire. In the hospital, his face is badly
```

当前版本候选：ID 35906；单 token repr：

```text
' severely'
```

末 12 输入 token + 该候选联合解码：

```text
 and he catches fire. In the hospital, his face is severely
```


## S051

文档 `imdb_test:4432`；域 reviews；位置 39（从 0 开始）；参考 Logit Margin 0.002328872681。

输入前缀末 64 token：

```text
<|begin_of_text|>National Lampoon's Dorm Daze is easily the worst movie I have ever seen, and I've seen the movie Kazaam. Anyone reading this who thinks this movie was good in any way
```

参考版本候选：ID 11；单 token repr：

```text
','
```

末 12 输入 token + 该候选联合解码：

```text
 Anyone reading this who thinks this movie was good in any way,
```

当前版本候选：ID 374；单 token repr：

```text
' is'
```

末 12 输入 token + 该候选联合解码：

```text
 Anyone reading this who thinks this movie was good in any way is
```


## S052

文档 `c4_official_validation_first10000:2549`；域 web；位置 28（从 0 开始）；参考 Logit Margin 0.01177406311。

输入前缀末 64 token：

```text
<|begin_of_text|>In this episode we sit down with CEO Haize and Johnnie from The B.R.E.A.K.S and The Awakened Soul Podcast
```

参考版本候选：ID 82；单 token repr：

```text
's'
```

末 12 输入 token + 该候选联合解码：

```text
.R.E.A.K.S and The Awakened Soul Podcasts
```

当前版本候选：ID 311；单 token repr：

```text
' to'
```

末 12 输入 token + 该候选联合解码：

```text
.R.E.A.K.S and The Awakened Soul Podcast to
```


## S053

文档 `ag_news_test:997`；域 news；位置 10（从 0 开始）；参考 Logit Margin 0.0156211853。

输入前缀末 64 token：

```text
<|begin_of_text|>Roddick blisters junior champ By the time
```

参考版本候选：ID 279；单 token repr：

```text
' the'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Roddick blisters junior champ By the time the
```

当前版本候选：ID 25871；单 token repr：

```text
' Andy'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Roddick blisters junior champ By the time Andy
```


## S054

文档 `imdb_test:6383`；域 reviews；位置 11（从 0 开始）；参考 Logit Margin 0.003383636475。

输入前缀末 64 token：

```text
<|begin_of_text|>The funniest thing about Fortunes is that one of
```

参考版本候选：ID 279；单 token repr：

```text
' the'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>The funniest thing about Fortunes is that one of the
```

当前版本候选：ID 1124；单 token repr：

```text
' them'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>The funniest thing about Fortunes is that one of them
```


## S055

文档 `c4_official_validation_first10000:9721`；域 web；位置 81（从 0 开始）；参考 Logit Margin 0.008634567261。

输入前缀末 64 token：

```text
. From music, to art, to food, and overall family fun, Nebraska’s celebrations have something to please everyone. To make it a little easier on you, we’ve selected our 10 favorite festivals. Mark your calendar!
Arbor Day is celebrated every year on the last Friday in April in Nebraska’s hometown of
```

参考版本候选：ID 25379；单 token repr：

```text
' Lincoln'
```

末 12 输入 token + 该候选联合解码：

```text
 year on the last Friday in April in Nebraska’s hometown of Lincoln
```

当前版本候选：ID 38379；单 token repr：

```text
' Nebraska'
```

末 12 输入 token + 该候选联合解码：

```text
 year on the last Friday in April in Nebraska’s hometown of Nebraska
```


## S056

文档 `c4_official_validation_first10000:9780`；域 web；位置 83（从 0 开始）；参考 Logit Margin 0.007732391357。

输入前缀末 64 token：

```text
 Kansas from Kansas City, Missouri to Burlington, Colorado, right near the Kansas-Colorado border. Many of businesses in the small towns along this 437-mile stretch of highway find it difficult to get an ATM installed at their business due to the fact that other ATM companies don’t travel this far from the major cities. Not
```

参考版本候选：ID 2394；单 token repr：

```text
' Pr'
```

末 12 输入 token + 该候选联合解码：

```text
 companies don’t travel this far from the major cities. Not Pr
```

当前版本候选：ID 1193；单 token repr：

```text
' only'
```

末 12 输入 token + 该候选联合解码：

```text
 companies don’t travel this far from the major cities. Not only
```


## S057

文档 `ag_news_test:4284`；域 news；位置 40（从 0 开始）；参考 Logit Margin 0.00128364563。

输入前缀末 64 token：

```text
<|begin_of_text|>Software giant Microsoft rings up multibillion dollar profit gain REDMOND, Washington, Oct 21 (AFP) - The world #39;s biggest software company, Microsoft Corp, said Thursday that its
```

参考版本候选：ID 51534；单 token repr：

```text
' quarterly'
```

末 12 输入 token + 该候选联合解码：

```text
;s biggest software company, Microsoft Corp, said Thursday that its quarterly
```

当前版本候选：ID 4272；单 token repr：

```text
' net'
```

末 12 输入 token + 该候选联合解码：

```text
;s biggest software company, Microsoft Corp, said Thursday that its net
```


## S058

文档 `c4_official_validation_first10000:8541`；域 web；位置 74（从 0 开始）；参考 Logit Margin 0.0002784729004。

输入前缀末 64 token：

```text
 recent trends in order to target customers in the right way. When talking about marketing strategy, the change adopted, technologies used, and the rate of change varies depending on the industry the company operates within and who their customers are. However, since the boom of the internet and mobile usage in the late 20th century,
```

参考版本候选：ID 279；单 token repr：

```text
' the'
```

末 12 输入 token + 该候选联合解码：

```text
 internet and mobile usage in the late 20th century, the
```

当前版本候选：ID 8661；单 token repr：

```text
' marketing'
```

末 12 输入 token + 该候选联合解码：

```text
 internet and mobile usage in the late 20th century, marketing
```


## S059

文档 `imdb_test:6605`；域 reviews；位置 108（从 0 开始）；参考 Logit Margin 0.006160736084。

输入前缀末 64 token：

```text
 the first time around.<br /><br />I didn't.<br /><br />The writing is half-baked, and although at first the quality of the acting is stable enough to keep the movie on its feet (albeit shakily), the further we get into the plot the sillier it gets. The
```

参考版本候选：ID 5885；单 token repr：

```text
' characters'
```

末 12 输入 token + 该候选联合解码：

```text
 we get into the plot the sillier it gets. The characters
```

当前版本候选：ID 7234；单 token repr：

```text
' plot'
```

末 12 输入 token + 该候选联合解码：

```text
 we get into the plot the sillier it gets. The plot
```


## S060

文档 `c4_official_validation_first10000:7411`；域 web；位置 40（从 0 开始）；参考 Logit Margin 0.02945518494。

输入前缀末 64 token：

```text
<|begin_of_text|>Disabilities Awareness Day was held recently. Description of the event; Varsity team won first place in Illinois State Science Olympiad held April 10 a the University of Illinois at Urbana-Champaign.
```

参考版本候选：ID 7817；单 token repr：

```text
' Description'
```

末 12 输入 token + 该候选联合解码：

```text
10 a the University of Illinois at Urbana-Champaign. Description
```

当前版本候选：ID 578；单 token repr：

```text
' The'
```

末 12 输入 token + 该候选联合解码：

```text
10 a the University of Illinois at Urbana-Champaign. The
```


## S061

文档 `c4_official_validation_first10000:2741`；域 web；位置 50（从 0 开始）；参考 Logit Margin 0.01897239685。

输入前缀末 64 token：

```text
<|begin_of_text|>Uprising Art is media partner of the first edition of the BIAC, Biennale Internationale d’Art Contemporain de Martinique, that takes place between November 22, 2013 and January 15, 2014 and
```

参考版本候选：ID 690；单 token repr：

```text
' will'
```

末 12 输入 token + 该候选联合解码：

```text
 2013 and January 15, 2014 and will
```

当前版本候选：ID 374；单 token repr：

```text
' is'
```

末 12 输入 token + 该候选联合解码：

```text
 2013 and January 15, 2014 and is
```


## S062

文档 `imdb_test:6787`；域 reviews；位置 73（从 0 开始）；参考 Logit Margin 0.001996040344。

输入前缀末 64 token：

```text
 19, I have seen many and dislike only one or two. This one though, the second it finished, I had to pull my sister (who had wanted to see it) out by the arm and I burst into tears of laughter as soon as I got out because it was such a ridiculously awful movie. <
```

参考版本候选：ID 64；单 token repr：

```text
'a'
```

末 12 输入 token + 该候选联合解码：

```text
 got out because it was such a ridiculously awful movie. <a
```

当前版本候选：ID 79；单 token repr：

```text
'p'
```

末 12 输入 token + 该候选联合解码：

```text
 got out because it was such a ridiculously awful movie. <p
```


## S063

文档 `c4_official_validation_first10000:4844`；域 web；位置 95（从 0 开始）；参考 Logit Margin 0.01748371124。

输入前缀末 64 token：

```text
 of Sundial of the Exiled.
Drops from Coren Direbrew, in the Grim Guzzler inside BRD.
Currently DOES stack with Abyssal Rune. Makes for some pretty painful crits.
No flavour text for spellcasters this year too?
This trinket will sometimes proc this spell.
It
```

参考版本候选：ID 596；单 token repr：

```text
"'s"
```

末 12 输入 token + 该候选联合解码：

```text
?
This trinket will sometimes proc this spell.
It's
```

当前版本候选：ID 374；单 token repr：

```text
' is'
```

末 12 输入 token + 该候选联合解码：

```text
?
This trinket will sometimes proc this spell.
It is
```


## S064

文档 `c4_official_validation_first10000:1845`；域 web；位置 51（从 0 开始）；参考 Logit Margin 0.004997253418。

输入前缀末 64 token：

```text
<|begin_of_text|>HAUMING IMPORT&EXPORT CO., LTD. is a technical Taiwan Screen Printing Paste manufacturer, factory, supplier and exporter. Customers' satisfaction consists by quality and commitment. It has always been our focus to manufacture top quality products and to deliver them as per
```

参考版本候选：ID 6444；单 token repr：

```text
' customers'
```

末 12 输入 token + 该候选联合解码：

```text
 focus to manufacture top quality products and to deliver them as per customers
```

当前版本候选：ID 279；单 token repr：

```text
' the'
```

末 12 输入 token + 该候选联合解码：

```text
 focus to manufacture top quality products and to deliver them as per the
```


## S065

文档 `c4_official_validation_first10000:4632`；域 web；位置 2（从 0 开始）；参考 Logit Margin 0.01244926453。

输入前缀末 64 token：

```text
<|begin_of_text|>This chicken
```

参考版本候选：ID 1370；单 token repr：

```text
' par'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>This chicken par
```

当前版本候选：ID 323；单 token repr：

```text
' and'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>This chicken and
```


## S066

文档 `c4_official_validation_first10000:9481`；域 web；位置 95（从 0 开始）；参考 Logit Margin 0.00341796875。

输入前缀末 64 token：

```text
 But what is it that makes chai such an excellent wellness tonic? A powerful blend of tea, herbs and spices, chai has been cherished for centuries in the East as a soothing way to preserve health and increase peace of mind. But the more we learn about the ingredients in chai, the more benefits we discover. Chai
```

参考版本候选：ID 374；单 token repr：

```text
' is'
```

末 12 输入 token + 该候选联合解码：

```text
 ingredients in chai, the more benefits we discover. Chai is
```

当前版本候选：ID 15600；单 token repr：

```text
' tea'
```

末 12 输入 token + 该候选联合解码：

```text
 ingredients in chai, the more benefits we discover. Chai tea
```


## S067

文档 `imdb_test:11232`；域 reviews；位置 55（从 0 开始）；参考 Logit Margin 0.01441478729。

输入前缀末 64 token：

```text
<|begin_of_text|>This is a rip-off of already crappy hollywood movies like Scream and I Know What You Did Last Summer. The story is classic, some high-school students tries a prank on the class' asthmatic misfit but something goes wrong. Terribly wrong. When you
```

参考版本候选：ID 3821；单 token repr：

```text
' watch'
```

末 12 输入 token + 该候选联合解码：

```text
fit but something goes wrong. Terribly wrong. When you watch
```

当前版本候选：ID 1456；单 token repr：

```text
' try'
```

末 12 输入 token + 该候选联合解码：

```text
fit but something goes wrong. Terribly wrong. When you try
```


## S068

文档 `c4_official_validation_first10000:1467`；域 web；位置 86（从 0 开始）；参考 Logit Margin 0.01078224182。

输入前缀末 64 token：

```text
 out their new amazing products and giveaway!
I received this award from Adriann and it really made my day.
All you need to do is pick 6 or more people who inspire you on a daily basis and tell them THANK YOU!
1. Milliande: She is a beautiful,talented artist who's spirit shines
```

参考版本候选：ID 10107；单 token repr：

```text
' bright'
```

末 12 输入 token + 该候选联合解码：

```text
 She is a beautiful,talented artist who's spirit shines bright
```

当前版本候选：ID 1555；单 token repr：

```text
' through'
```

末 12 输入 token + 该候选联合解码：

```text
 She is a beautiful,talented artist who's spirit shines through
```


## S069

文档 `imdb_test:5044`；域 reviews；位置 65（从 0 开始）；参考 Logit Margin 0.01400375366。

输入前缀末 64 token：

```text
 music is totally out of touch with the film, showing up now and then as wagnerian bombast and Lone Ranger hurry-up, otherwise nonexistent. The acting, outside of the two principals, is nonexistent. It would have been an excellent student film. The Russian soldiers are just models trying to act. The constant interruptions
```

参考版本候选：ID 315；单 token repr：

```text
' of'
```

末 12 输入 token + 该候选联合解码：

```text
 Russian soldiers are just models trying to act. The constant interruptions of
```

当前版本候选：ID 555；单 token repr：

```text
' by'
```

末 12 输入 token + 该候选联合解码：

```text
 Russian soldiers are just models trying to act. The constant interruptions by
```


## S070

文档 `ag_news_test:4215`；域 news；位置 5（从 0 开始）；参考 Logit Margin 0.01179695129。

输入前缀末 64 token：

```text
<|begin_of_text|>Red Sox Slugger Ortiz
```

参考版本候选：ID 596；单 token repr：

```text
"'s"
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Red Sox Slugger Ortiz's
```

当前版本候选：ID 328；单 token repr：

```text
' S'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Red Sox Slugger Ortiz S
```


## S071

文档 `c4_official_validation_first10000:5772`；域 web；位置 24（从 0 开始）；参考 Logit Margin 0.004343032837。

输入前缀末 64 token：

```text
<|begin_of_text|>Continuous Sensor Monitoring. Bluetooth® Low Energy.
Select application area to start.
ON Semiconductor has the expertise, products, platforms
```

参考版本候选：ID 323；单 token repr：

```text
' and'
```

末 12 输入 token + 该候选联合解码：

```text
 to start.
ON Semiconductor has the expertise, products, platforms and
```

当前版本候选：ID 11；单 token repr：

```text
','
```

末 12 输入 token + 该候选联合解码：

```text
 to start.
ON Semiconductor has the expertise, products, platforms,
```


## S072

文档 `ag_news_test:997`；域 news；位置 48（从 0 开始）；参考 Logit Margin 0.04159355164。

输入前缀末 64 token：

```text
<|begin_of_text|>Roddick blisters junior champ By the time his match with Andy Roddick was over, Jenkins had felt the full fury of Roddick #39;s jet blast. Roddick had nailed a 152-mph serve at
```

参考版本候选：ID 832；单 token repr：

```text
' one'
```

末 12 输入 token + 该候选联合解码：

```text
 Roddick had nailed a 152-mph serve at one
```

当前版本候选：ID 220；单 token repr：

```text
' '
```

末 12 输入 token + 该候选联合解码：

```text
 Roddick had nailed a 152-mph serve at 
```


## S073

文档 `c4_official_validation_first10000:22`；域 web；位置 61（从 0 开始）；参考 Logit Margin 0.008827209473。

输入前缀末 64 token：

```text
<|begin_of_text|>Today we are delighted to introduce you to FarmGirlRosePetals, a three-generation family farm based in Oregon, growing gorgeous flowers and freeze drying the petals for eco-friendly celebrations!
How long have you been preserving flowers with freeze drying? When and where did the floriculture life begin for you?
I started
```

参考版本候选：ID 47995；单 token repr：

```text
' preserving'
```

末 12 输入 token + 该候选联合解码：

```text
 where did the floriculture life begin for you?
I started preserving
```

当前版本候选：ID 6975；单 token repr：

```text
' learning'
```

末 12 输入 token + 该候选联合解码：

```text
 where did the floriculture life begin for you?
I started learning
```


## S074

文档 `imdb_test:16440`；域 reviews；位置 39（从 0 开始）；参考 Logit Margin 0.001565933228。

输入前缀末 64 token：

```text
<|begin_of_text|>SPOILERS<br /><br />I love the Simpsons, and I have seen every single episode that had ever come out. I must admit, season one is by far the most underrated season
```

参考版本候选：ID 13；单 token repr：

```text
'.'
```

末 12 输入 token + 该候选联合解码：

```text
 must admit, season one is by far the most underrated season.
```

当前版本候选：ID 315；单 token repr：

```text
' of'
```

末 12 输入 token + 该候选联合解码：

```text
 must admit, season one is by far the most underrated season of
```


## S075

文档 `ag_news_test:958`；域 news；位置 28（从 0 开始）；参考 Logit Margin 0.03163146973。

输入前缀末 64 token：

```text
<|begin_of_text|>British Minister to Visit North Korea in September The British government has announced plans to send a top Foreign Office representative to North Korea in September. Junior
```

参考版本候选：ID 19620；单 token repr：

```text
' Foreign'
```

末 12 输入 token + 该候选联合解码：

```text
 a top Foreign Office representative to North Korea in September. Junior Foreign
```

当前版本候选：ID 9675；单 token repr：

```text
' Minister'
```

末 12 输入 token + 该候选联合解码：

```text
 a top Foreign Office representative to North Korea in September. Junior Minister
```


## S076

文档 `c4_official_validation_first10000:6146`；域 web；位置 37（从 0 开始）；参考 Logit Margin 0.0109500885。

输入前缀末 64 token：

```text
<|begin_of_text|>Since Sonya is interested in robotics too, she decided to construct robots that will read and recognize numbers.
Sonya has drawn $$$n$$$ numbers in a row, $$$a_i$$$
```

参考版本候选：ID 369；单 token repr：

```text
' for'
```

末 12 输入 token + 该候选联合解码：

```text
 $$$n$$$ numbers in a row, $$$a_i$$$ for
```

当前版本候选：ID 505；单 token repr：

```text
' from'
```

末 12 输入 token + 该候选联合解码：

```text
 $$$n$$$ numbers in a row, $$$a_i$$$ from
```


## S077

文档 `imdb_test:1726`；域 reviews；位置 6（从 0 开始）；参考 Logit Margin 0.02832508087。

输入前缀末 64 token：

```text
<|begin_of_text|>This is a disaster-movie
```

参考版本候选：ID 67265；单 token repr：

```text
' parody'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>This is a disaster-movie parody
```

当前版本候选：ID 15398；单 token repr：

```text
' scenario'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>This is a disaster-movie scenario
```


## S078

文档 `c4_official_validation_first10000:22`；域 web；位置 44（从 0 开始）；参考 Logit Margin 0.03169822693。

输入前缀末 64 token：

```text
<|begin_of_text|>Today we are delighted to introduce you to FarmGirlRosePetals, a three-generation family farm based in Oregon, growing gorgeous flowers and freeze drying the petals for eco-friendly celebrations!
How long have you been preserving flowers with
```

参考版本候选：ID 701；单 token repr：

```text
' your'
```

末 12 输入 token + 该候选联合解码：

```text
 eco-friendly celebrations!
How long have you been preserving flowers with your
```

当前版本候选：ID 31030；单 token repr：

```text
' freeze'
```

末 12 输入 token + 该候选联合解码：

```text
 eco-friendly celebrations!
How long have you been preserving flowers with freeze
```


## S079

文档 `ag_news_test:1675`；域 news；位置 4（从 0 开始）；参考 Logit Margin 0.008939743042。

输入前缀末 64 token：

```text
<|begin_of_text|>Ivan Roars
```

参考版本候选：ID 14077；单 token repr：

```text
' Again'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Ivan Roars Again
```

当前版本候选：ID 6984；单 token repr：

```text
' Back'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Ivan Roars Back
```


## S080

文档 `c4_official_validation_first10000:9192`；域 web；位置 65（从 0 开始）；参考 Logit Margin 0.01644897461。

输入前缀末 64 token：

```text
 McCormick Harvesting Machine Company, formed by Cyrus Hall McCormick, merged with several other manufacturers and formed the International Harvester Co. They were primarily known for the production of harvesting equipment. They began experimenting with tractors around 1905. These tractors were huge, powerful and clumsy and although they were useful for
```

参考版本候选：ID 3544；单 token repr：

```text
' large'
```

末 12 输入 token + 该候选联合解码：

```text
 were huge, powerful and clumsy and although they were useful for large
```

当前版本候选：ID 8987；单 token repr：

```text
' heavy'
```

末 12 输入 token + 该候选联合解码：

```text
 were huge, powerful and clumsy and although they were useful for heavy
```


## S081

文档 `imdb_test:20600`；域 reviews；位置 59（从 0 开始）；参考 Logit Margin 0.002680778503。

输入前缀末 64 token：

```text
<|begin_of_text|>Hey guy, this movies is everything about choices. All the times in your life you must pick something or it just pass away... And this movie prove that! Of course, life in fact is not like a beautiful picture as this movie shows... it not shows indeed but some may figure that.
```

参考版本候选：ID 358；单 token repr：

```text
' I'
```

末 12 输入 token + 该候选联合解码：

```text
 shows... it not shows indeed but some may figure that. I
```

当前版本候选：ID 2030；单 token repr：

```text
' But'
```

末 12 输入 token + 该候选联合解码：

```text
 shows... it not shows indeed but some may figure that. But
```


## S082

文档 `c4_official_validation_first10000:6228`；域 web；位置 36（从 0 开始）；参考 Logit Margin 0.01976394653。

输入前缀末 64 token：

```text
<|begin_of_text|>“The Bible says it; I believe it; that settles it” is a popular saying amongst some Christians. The problem is: does the Bible say it? It is quite possible for
```

参考版本候选：ID 1274；单 token repr：

```text
' people'
```

末 12 输入 token + 该候选联合解码：

```text
: does the Bible say it? It is quite possible for people
```

当前版本候选：ID 4423；单 token repr：

```text
' someone'
```

末 12 输入 token + 该候选联合解码：

```text
: does the Bible say it? It is quite possible for someone
```


## S083

文档 `c4_official_validation_first10000:9141`；域 web；位置 104（从 0 开始）；参考 Logit Margin 0.01100349426。

输入前缀末 64 token：

```text
 #LondonLife) as she stays true to her laid-back, edgy style.
On her first day in London, Julie Ann opted for a lace top, printed denim cut-offs, and a knitted cardigan.
We loved her olive green denim jacket worn over her button-front cropped top and floral printed shorts. For
```

参考版本候选：ID 264；单 token repr：

```text
' a'
```

末 12 输入 token + 该候选联合解码：

```text
 over her button-front cropped top and floral printed shorts. For a
```

当前版本候选：ID 23090；单 token repr：

```text
' accessories'
```

末 12 输入 token + 该候选联合解码：

```text
 over her button-front cropped top and floral printed shorts. For accessories
```


## S084

文档 `imdb_test:13876`；域 reviews；位置 18（从 0 开始）；参考 Logit Margin 0.006918907166。

输入前缀末 64 token：

```text
<|begin_of_text|>I saw this originally on Channel 4 (UK) and it was a fantastic film that
```

参考版本候选：ID 2216；单 token repr：

```text
' really'
```

末 12 输入 token + 该候选联合解码：

```text
 4 (UK) and it was a fantastic film that really
```

当前版本候选：ID 358；单 token repr：

```text
' I'
```

末 12 输入 token + 该候选联合解码：

```text
 4 (UK) and it was a fantastic film that I
```


## S085

文档 `c4_official_validation_first10000:8513`；域 web；位置 121（从 0 开始）；参考 Logit Margin 0.001800537109。

输入前缀末 64 token：

```text
 gosh I was just dying hearing these roasts.
Donald things he knows about Global Warming but he's just making one chilling mistake after the next. First he claims he wants a wall and Mexico is paying for it but wait now what do we have here. We have American Federal workers not working, not getting paid
```

参考版本候选：ID 323；单 token repr：

```text
' and'
```

末 12 输入 token + 该候选联合解码：

```text
. We have American Federal workers not working, not getting paid and
```

当前版本候选：ID 11；单 token repr：

```text
','
```

末 12 输入 token + 该候选联合解码：

```text
. We have American Federal workers not working, not getting paid,
```


## S086

文档 `imdb_test:3032`；域 reviews；位置 41（从 0 开始）；参考 Logit Margin 0.0149230957。

输入前缀末 64 token：

```text
<|begin_of_text|>This was without a doubt the WORST movie I have ever see, yet once I started, it was just like the really bad car wreck on the side of the road - you can't help yourself
```

参考版本候选：ID 505；单 token repr：

```text
' from'
```

末 12 输入 token + 该候选联合解码：

```text
 on the side of the road - you can't help yourself from
```

当前版本候选：ID 719；单 token repr：

```text
' but'
```

末 12 输入 token + 该候选联合解码：

```text
 on the side of the road - you can't help yourself but
```


## S087

文档 `imdb_test:12099`；域 reviews；位置 59（从 0 开始）；参考 Logit Margin 0.04506206512。

输入前缀末 64 token：

```text
<|begin_of_text|>First, what is really great about this movie: <br /><br />- Ryan Reynolds, great acting! There are very few actors I really like and for now he is one of them. He has an amazing skill to impersonate characters. <br /><br />- The soundtrack! Very
```

参考版本候选：ID 6555；单 token repr：

```text
' nice'
```

末 12 输入 token + 该候选联合解码：

```text
 characters. <br /><br />- The soundtrack! Very nice
```

当前版本候选：ID 86605；单 token repr：

```text
' catchy'
```

末 12 输入 token + 该候选联合解码：

```text
 characters. <br /><br />- The soundtrack! Very catchy
```


## S088

文档 `c4_official_validation_first10000:1340`；域 web；位置 95（从 0 开始）；参考 Logit Margin 0.002000808716。

输入前缀末 64 token：

```text
2015/03/26/when-klekolo-was-the-center-of-the-universe-2/), the home of my spiritual rebirth and purveyors of fine bean. So it seems only right that one of our rare gigs (Julie Kay and Myself, of course) is at this very
```

参考版本候选：ID 11033；单 token repr：

```text
' coffee'
```

末 12 输入 token + 该候选联合解码：

```text
 Kay and Myself, of course) is at this very coffee
```

当前版本候选：ID 1890；单 token repr：

```text
' same'
```

末 12 输入 token + 该候选联合解码：

```text
 Kay and Myself, of course) is at this very same
```


## S089

文档 `imdb_test:16238`；域 reviews；位置 11（从 0 开始）；参考 Logit Margin 0.01440620422。

输入前缀末 64 token：

```text
<|begin_of_text|>Obviously the previous reviewers here are not fans of this genre
```

参考版本候选：ID 11；单 token repr：

```text
','
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Obviously the previous reviewers here are not fans of this genre,
```

当前版本候选：ID 13；单 token repr：

```text
'.'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Obviously the previous reviewers here are not fans of this genre.
```


## S090

文档 `c4_official_validation_first10000:1737`；域 web；位置 31（从 0 开始）；参考 Logit Margin 0.03488636017。

输入前缀末 64 token：

```text
<|begin_of_text|>I have a feeling the ratings success or failure of upcoming sageuk Saimdang: Light’s Diary won’t have any affect on the star power or
```

参考版本候选：ID 7076；单 token repr：

```text
' career'
```

末 12 输入 token + 该候选联合解码：

```text
’s Diary won’t have any affect on the star power or career
```

当前版本候选：ID 23354；单 token repr：

```text
' popularity'
```

末 12 输入 token + 该候选联合解码：

```text
’s Diary won’t have any affect on the star power or popularity
```


## S091

文档 `c4_official_validation_first10000:6218`；域 web；位置 13（从 0 开始）；参考 Logit Margin 0.0371055603。

输入前缀末 64 token：

```text
<|begin_of_text|>Looking for an award winning digital agency providing dedicated Branding services to
```

参考版本候选：ID 8403；单 token repr：

```text
' clients'
```

末 12 输入 token + 该候选联合解码：

```text
 for an award winning digital agency providing dedicated Branding services to clients
```

当前版本候选：ID 499；单 token repr：

```text
' you'
```

末 12 输入 token + 该候选联合解码：

```text
 for an award winning digital agency providing dedicated Branding services to you
```


## S092

文档 `c4_official_validation_first10000:6090`；域 web；位置 85（从 0 开始）；参考 Logit Margin 0.002208709717。

输入前缀末 64 token：

```text
 Courting Charlie Oldman?
Kiernan Shipka is formally taken and no, Sabrina enthusiasts, we are sorry to mention that it isn’t by way of her on-screen love passion, Ross Lynch. The 19-year-old Chilling Adventures of Sabrina megastar sparked rumours of a courting previous this
```

参考版本候选：ID 43438；单 token repr：

```text
' yr'
```

末 12 输入 token + 该候选联合解码：

```text
rina megastar sparked rumours of a courting previous this yr
```

当前版本候选：ID 2046；单 token repr：

```text
' week'
```

末 12 输入 token + 该候选联合解码：

```text
rina megastar sparked rumours of a courting previous this week
```


## S093

文档 `c4_official_validation_first10000:2711`；域 web；位置 103（从 0 开始）；参考 Logit Margin 0.005318641663。

输入前缀末 64 token：

```text
 been taking action and fighting for the environment. This legendary boat has become a platform of top-quality scientific research.
Tara Expeditions was born both from a passion for the sea and from the committed humanist vision of Agnès B and Etienne Bourgois. In collaboration with various scientific institutions, the expeditions
```

参考版本候选：ID 9395；单 token repr：

```text
' aim'
```

末 12 输入 token + 该候选联合解码：

```text
is. In collaboration with various scientific institutions, the expeditions aim
```

当前版本候选：ID 617；单 token repr：

```text
' have'
```

末 12 输入 token + 该候选联合解码：

```text
is. In collaboration with various scientific institutions, the expeditions have
```


## S094

文档 `imdb_test:7038`；域 reviews；位置 64（从 0 开始）；参考 Logit Margin 0.01734447479。

输入前缀末 64 token：

```text
Oh God, Why? I am aghast at the sheer ineptitude of this delicious blathering nonsense..as if all that makes sense. Well, like this film from bottom rung poverty row of 1940s Hollywood, nothing in this door slamming horror - made on three sets - makes much sense...
```

参考版本候选：ID 11945；单 token repr：

```text
'except'
```

末 12 输入 token + 该候选联合解码：

```text
 slamming horror - made on three sets - makes much sense...except
```

当前版本候选：ID 438；单 token repr：

```text
'and'
```

末 12 输入 token + 该候选联合解码：

```text
 slamming horror - made on three sets - makes much sense...and
```


## S095

文档 `imdb_test:9422`；域 reviews；位置 21（从 0 开始）；参考 Logit Margin 0.009369850159。

输入前缀末 64 token：

```text
<|begin_of_text|>If you're a North American 'TOURIST' looking for a 'TRAP' here it is
```

参考版本候选：ID 13；单 token repr：

```text
'.'
```

末 12 输入 token + 该候选联合解码：

```text
IST' looking for a 'TRAP' here it is.
```

当前版本候选：ID 4999；单 token repr：

```text
'!\n'
```

末 12 输入 token + 该候选联合解码：

```text
IST' looking for a 'TRAP' here it is!

```


## S096

文档 `c4_official_validation_first10000:1992`；域 web；位置 26（从 0 开始）；参考 Logit Margin 0.01017284393。

输入前缀末 64 token：

```text
<|begin_of_text|>as a franchise stockpiling draft picks Anthony Beauvillier Jersey Womens , Vegas Golden Knights general manager George McPhee is
```

参考版本候选：ID 3411；单 token repr：

```text
' looking'
```

末 12 输入 token + 该候选联合解码：

```text
 Womens , Vegas Golden Knights general manager George McPhee is looking
```

当前版本候选：ID 539；单 token repr：

```text
' not'
```

末 12 输入 token + 该候选联合解码：

```text
 Womens , Vegas Golden Knights general manager George McPhee is not
```


## S097

文档 `c4_official_validation_first10000:3962`；域 web；位置 123（从 0 开始）；参考 Logit Margin 0.01379203796。

输入前缀末 64 token：

```text
0, up from just under 40% at the end of 2014. Smartphone adoption is already reaching critical mass in developed markets, with the devices now accounting for 60% of connections. It is the developing world—driven by the increased affordability of devices—that will produce most of the future growth, adding
```

参考版本候选：ID 927；单 token repr：

```text
' over'
```

末 12 输入 token + 该候选联合解码：

```text
 of devices—that will produce most of the future growth, adding over
```

当前版本候选：ID 220；单 token repr：

```text
' '
```

末 12 输入 token + 该候选联合解码：

```text
 of devices—that will produce most of the future growth, adding 
```


## S098

文档 `c4_official_validation_first10000:7914`；域 web；位置 74（从 0 开始）；参考 Logit Margin 0.0176486969。

输入前缀末 64 token：

```text
. Some we can’t even remember, being born for example, when we first learn to walk, talk, eat without spitting up. Others are very memorable, our first day or school, our drivers test, that time in college when we realize we actually haven’t learned how to eat without spitting up. These
```

参考版本候选：ID 527；单 token repr：

```text
' are'
```

末 12 输入 token + 该候选联合解码：

```text
 haven’t learned how to eat without spitting up. These are
```

当前版本候选：ID 14269；单 token repr：

```text
' moments'
```

末 12 输入 token + 该候选联合解码：

```text
 haven’t learned how to eat without spitting up. These moments
```


## S099

文档 `c4_official_validation_first10000:5589`；域 web；位置 96（从 0 开始）；参考 Logit Margin 0.005674362183。

输入前缀末 64 token：

```text
 you support the right of everyone to share their opinions and made a grand “free speech for all” declaration, however, I think you are confusing the validity of sharing opinions with making false statements.
For example, there has been lots of debate about the expansion of bike lanes in downtown Victoria – there are both pros and cons
```

参考版本候选：ID 13；单 token repr：

```text
'.'
```

末 12 输入 token + 该候选联合解码：

```text
 bike lanes in downtown Victoria – there are both pros and cons.
```

当前版本候选：ID 311；单 token repr：

```text
' to'
```

末 12 输入 token + 该候选联合解码：

```text
 bike lanes in downtown Victoria – there are both pros and cons to
```


## S100

文档 `c4_official_validation_first10000:7387`；域 web；位置 1（从 0 开始）；参考 Logit Margin 0.008631706238。

输入前缀末 64 token：

```text
<|begin_of_text|>Premium
```

参考版本候选：ID 4367；单 token repr：

```text
' quality'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Premium quality
```

当前版本候选：ID 13659；单 token repr：

```text
' Article'
```

末 12 输入 token + 该候选联合解码：

```text
<|begin_of_text|>Premium Article
```

