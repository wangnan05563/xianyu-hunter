/*
   Licensed to the Apache Software Foundation (ASF) under one or more
   contributor license agreements.  See the NOTICE file distributed with
   this work for additional information regarding copyright ownership.
   The ASF licenses this file to You under the Apache License, Version 2.0
   (the "License"); you may not use this file except in compliance with
   the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/
var showControllersOnly = false;
var seriesFilter = "";
var filtersOnlySampleSeries = true;

/*
 * Add header in statistics table to group metrics by category
 * format
 *
 */
function summaryTableHeader(header) {
    var newRow = header.insertRow(-1);
    newRow.className = "tablesorter-no-sort";
    var cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Requests";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 3;
    cell.innerHTML = "Executions";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 7;
    cell.innerHTML = "Response Times (ms)";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Throughput";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 2;
    cell.innerHTML = "Network (KB/sec)";
    newRow.appendChild(cell);
}

/*
 * Populates the table identified by id parameter with the specified data and
 * format
 *
 */
function createTable(table, info, formatter, defaultSorts, seriesIndex, headerCreator) {
    var tableRef = table[0];

    // Create header and populate it with data.titles array
    var header = tableRef.createTHead();

    // Call callback is available
    if(headerCreator) {
        headerCreator(header);
    }

    var newRow = header.insertRow(-1);
    for (var index = 0; index < info.titles.length; index++) {
        var cell = document.createElement('th');
        cell.innerHTML = info.titles[index];
        newRow.appendChild(cell);
    }

    var tBody;

    // Create overall body if defined
    if(info.overall){
        tBody = document.createElement('tbody');
        tBody.className = "tablesorter-no-sort";
        tableRef.appendChild(tBody);
        var newRow = tBody.insertRow(-1);
        var data = info.overall.data;
        for(var index=0;index < data.length; index++){
            var cell = newRow.insertCell(-1);
            cell.innerHTML = formatter ? formatter(index, data[index]): data[index];
        }
    }

    // Create regular body
    tBody = document.createElement('tbody');
    tableRef.appendChild(tBody);

    var regexp;
    if(seriesFilter) {
        regexp = new RegExp(seriesFilter, 'i');
    }
    // Populate body with data.items array
    for(var index=0; index < info.items.length; index++){
        var item = info.items[index];
        if((!regexp || filtersOnlySampleSeries && !info.supportsControllersDiscrimination || regexp.test(item.data[seriesIndex]))
                &&
                (!showControllersOnly || !info.supportsControllersDiscrimination || item.isController)){
            if(item.data.length > 0) {
                var newRow = tBody.insertRow(-1);
                for(var col=0; col < item.data.length; col++){
                    var cell = newRow.insertCell(-1);
                    cell.innerHTML = formatter ? formatter(col, item.data[col]) : item.data[col];
                }
            }
        }
    }

    // Add support of columns sort
    table.tablesorter({sortList : defaultSorts});
}

$(document).ready(function() {

    // Customize table sorter default options
    $.extend( $.tablesorter.defaults, {
        theme: 'blue',
        cssInfoBlock: "tablesorter-no-sort",
        widthFixed: true,
        widgets: ['zebra']
    });

    var data = {"OkPercent": 95.1102686396804, "KoPercent": 4.889731360319596};
    var dataset = [
        {
            "label" : "FAIL",
            "data" : data.KoPercent,
            "color" : "#FF6347"
        },
        {
            "label" : "PASS",
            "data" : data.OkPercent,
            "color" : "#9ACD32"
        }];
    $.plot($("#flot-requests-summary"), dataset, {
        series : {
            pie : {
                show : true,
                radius : 1,
                label : {
                    show : true,
                    radius : 3 / 4,
                    formatter : function(label, series) {
                        return '<div style="font-size:8pt;text-align:center;padding:2px;color:white;">'
                            + label
                            + '<br/>'
                            + Math.round10(series.percent, -2)
                            + '%</div>';
                    },
                    background : {
                        opacity : 0.5,
                        color : '#000'
                    }
                }
            }
        },
        legend : {
            show : true
        }
    });

    // Creates APDEX table
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.6605825282295871, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.7192737430167597, 500, 1500, "账号"], "isController": false}, {"data": [0.7949640287769785, 500, 1500, "反爬指纹"], "isController": false}, {"data": [0.7579075425790754, 500, 1500, "任务运行记录"], "isController": false}, {"data": [0.6501706484641638, 500, 1500, "价格趋势"], "isController": false}, {"data": [0.0, 500, 1500, "偏好"], "isController": false}, {"data": [0.887627695800227, 500, 1500, "趋势"], "isController": false}, {"data": [0.7152875175315568, 500, 1500, "账号统计"], "isController": false}, {"data": [0.7693823915900131, 500, 1500, "配置导出"], "isController": false}, {"data": [0.7724514563106796, 500, 1500, "任务详情"], "isController": false}, {"data": [0.0, 500, 1500, "维护状态"], "isController": false}, {"data": [0.7503022974607013, 500, 1500, "任务列表"], "isController": false}, {"data": [0.7727272727272727, 500, 1500, "客服配置"], "isController": false}, {"data": [0.0, 500, 1500, "订单详情"], "isController": false}, {"data": [0.07095046854082998, 500, 1500, "检查更新"], "isController": false}, {"data": [0.7302110817941952, 500, 1500, "配置分享"], "isController": false}, {"data": [0.7431906614785992, 500, 1500, "评估卖家价格趋势"], "isController": false}, {"data": [0.8926974664679582, 500, 1500, "知识库版本"], "isController": false}, {"data": [0.7770700636942676, 500, 1500, "评估分布"], "isController": false}, {"data": [0.6961942257217848, 500, 1500, "配置版本"], "isController": false}, {"data": [0.7858347386172007, 500, 1500, "批量刷新状态"], "isController": false}, {"data": [0.5878284923928078, 500, 1500, "日志"], "isController": false}, {"data": [0.06222547584187409, 500, 1500, "向量库状态"], "isController": false}, {"data": [0.7807351077313055, 500, 1500, "评估列表"], "isController": false}, {"data": [0.685378590078329, 500, 1500, "配置备份"], "isController": false}, {"data": [0.8122676579925651, 500, 1500, "近期反馈"], "isController": false}, {"data": [0.7606516290726817, 500, 1500, "商品摘要"], "isController": false}, {"data": [0.15201192250372578, 500, 1500, "隧道状态"], "isController": false}, {"data": [0.683288409703504, 500, 1500, "通知列表"], "isController": false}, {"data": [0.7125827814569536, 500, 1500, "Prompt列表"], "isController": false}, {"data": [0.5889830508474576, 500, 1500, "批量刷新历史"], "isController": false}, {"data": [0.7924187725631769, 500, 1500, "砍价评估"], "isController": false}, {"data": [0.7951289398280802, 500, 1500, "反爬频率统计"], "isController": false}, {"data": [0.6687388987566607, 500, 1500, "DB表列表"], "isController": false}, {"data": [0.6177829099307159, 500, 1500, "价格分类统计"], "isController": false}, {"data": [0.8452380952380952, 500, 1500, "知识库状态"], "isController": false}, {"data": [0.8062857142857143, 500, 1500, "卖家价格趋势"], "isController": false}, {"data": [0.7574193548387097, 500, 1500, "阈值建议"], "isController": false}, {"data": [0.6743243243243243, 500, 1500, "未读计数"], "isController": false}, {"data": [0.7364130434782609, 500, 1500, "DB表行"], "isController": false}, {"data": [0.6948051948051948, 500, 1500, "配置"], "isController": false}, {"data": [0.7327348066298343, 500, 1500, "错误日志详情"], "isController": false}, {"data": [0.7374839537869063, 500, 1500, "反馈统计"], "isController": false}, {"data": [0.6756756756756757, 500, 1500, "DB表结构"], "isController": false}, {"data": [0.7729528535980149, 500, 1500, "订单列表"], "isController": false}, {"data": [0.4618585298196949, 500, 1500, "日志搜索"], "isController": false}, {"data": [0.0, 500, 1500, "反爬策略"], "isController": false}, {"data": [0.7952548330404218, 500, 1500, "参数计算器规则"], "isController": false}, {"data": [0.6029668411867365, 500, 1500, "Cron示例"], "isController": false}, {"data": [0.8696868008948546, 500, 1500, "Dashboard统计"], "isController": false}, {"data": [0.8958333333333334, 500, 1500, "今日统计"], "isController": false}, {"data": [0.49588477366255146, 500, 1500, "错误日志"], "isController": false}, {"data": [0.7804232804232805, 500, 1500, "菜单"], "isController": false}, {"data": [0.6496478873239436, 500, 1500, "价格分类对比"], "isController": false}, {"data": [0.7992036405005688, 500, 1500, "评估漏斗"], "isController": false}, {"data": [0.6206690561529271, 500, 1500, "售出区间"], "isController": false}, {"data": [0.8765020026702269, 500, 1500, "关于"], "isController": false}, {"data": [0.7656058751529988, 500, 1500, "任务预检"], "isController": false}, {"data": [0.7559840425531915, 500, 1500, "模板"], "isController": false}, {"data": [0.8873159682899208, 500, 1500, "业务KPI"], "isController": false}, {"data": [0.7557544757033248, 500, 1500, "自动采集统计"], "isController": false}, {"data": [0.7288686605981795, 500, 1500, "配置原始"], "isController": false}, {"data": [0.7723948811700183, 500, 1500, "会话列表"], "isController": false}, {"data": [0.8127147766323024, 500, 1500, "价格直方图"], "isController": false}, {"data": [0.7636248415716096, 500, 1500, "最新评估"], "isController": false}, {"data": [0.0018796992481203006, 500, 1500, "商品批量"], "isController": false}, {"data": [0.8523391812865497, 500, 1500, "反爬健康"], "isController": false}]}, function(index, item){
        switch(index){
            case 0:
                item = item.toFixed(3);
                break;
            case 1:
            case 2:
                item = formatDuration(item);
                break;
        }
        return item;
    }, [[0, 0]], 3);

    // Create statistics table
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 49062, 2399, 4.889731360319596, 1222.689800660384, 1, 38929, 757.0, 5264.800000000003, 8731.0, 19117.400000000416, 79.58822155315615, 3447.8348608428855, 19.826073187134195], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["账号", 716, 0, 0.0, 984.6368715083803, 4, 12939, 284.0, 2633.2000000000007, 4869.75, 11344.180000000002, 1.185459903805558, 0.22458908333816235, 0.2882612461402187], "isController": false}, {"data": ["反爬指纹", 695, 0, 0.0, 573.9165467625902, 2, 19509, 195.0, 1536.9999999999995, 2506.9999999999973, 4448.239999999999, 1.147752963927528, 0.312717848570098, 0.2936633560048949], "isController": false}, {"data": ["任务运行记录", 822, 0, 0.0, 806.784671532847, 6, 12739, 252.0, 2050.3, 3665.3999999999996, 10266.34, 1.3434336005491407, 0.34635397514157534, 0.34241813451496655], "isController": false}, {"data": ["价格趋势", 879, 0, 0.0, 1350.3321956769048, 9, 21759, 461.0, 3337.0, 6285.0, 13165.400000000005, 1.4550595183901975, 0.5925388859069457, 0.3666067927194052], "isController": false}, {"data": ["偏好", 756, 756, 100.0, 409.5978835978836, 2, 11753, 69.0, 941.5000000000003, 2161.3999999999983, 5190.749999999984, 1.2607816846444797, 0.24378395855430365, 0.31027049270547735], "isController": false}, {"data": ["趋势", 881, 0, 0.0, 421.81498297389317, 1, 12561, 73.0, 782.8000000000014, 2198.699999999998, 6196.1199999999935, 1.4505782554861824, 2.379854950407018, 0.3569782425610527], "isController": false}, {"data": ["账号统计", 713, 1, 0.1402524544179523, 1241.8555399719492, 4, 30006, 270.0, 3364.800000000001, 5800.999999999989, 16947.700000000048, 1.1722519897867751, 0.2522443801162716, 0.2915087976443161], "isController": false}, {"data": ["配置导出", 761, 0, 0.0, 712.9198423127463, 36, 9907, 273.0, 2020.200000000001, 2882.599999999999, 6820.0, 1.2552039005337503, 13.050933524397305, 0.31134940501520764], "isController": false}, {"data": ["任务详情", 824, 1, 0.12135922330097088, 852.4987864077667, 3, 30006, 189.0, 2256.5, 4029.5, 9915.25, 1.3465262401032774, 0.9799855634493295, 0.336223026579186], "isController": false}, {"data": ["维护状态", 647, 3, 0.46367851622874806, 11497.225656877905, 1960, 30014, 11149.0, 19507.600000000002, 21929.0, 27780.879999999943, 1.0632633474882662, 0.4560717503500388, 0.26768389156028555], "isController": false}, {"data": ["任务列表", 827, 0, 0.0, 727.012091898428, 7, 14116, 255.0, 1861.2000000000005, 2887.7999999999997, 6155.920000000013, 1.3516163828326742, 1.0783892429436472, 0.3484635986990488], "isController": false}, {"data": ["客服配置", 539, 0, 0.0, 1186.9165120593682, 4, 20260, 206.0, 3776.0, 6360.0, 17534.800000000112, 0.8953934581457548, 1.429656546941708, 0.2229739568624682], "isController": false}, {"data": ["订单详情", 804, 804, 100.0, 1051.5733830845768, 19, 14435, 496.5, 2801.5, 4057.5, 7400.850000000013, 1.3237901891340536, 0.37619428226368123, 0.35033900513215677], "isController": false}, {"data": ["检查更新", 747, 0, 0.0, 4267.544846050873, 848, 38929, 3572.0, 7893.4000000000015, 9500.6, 17584.239999999998, 1.2244255690218693, 0.42328774554076337, 0.3096935765397111], "isController": false}, {"data": ["配置分享", 758, 0, 0.0, 923.8166226912932, 27, 14501, 304.0, 2502.900000000001, 4002.1499999999996, 10370.849999999988, 1.2423317156797669, 11.069369701037298, 0.30694328522166114], "isController": false}, {"data": ["评估卖家价格趋势", 771, 0, 0.0, 823.3592736705581, 3, 20710, 203.0, 2471.600000000003, 3565.1999999999985, 8074.36, 1.271295435208453, 0.328997353838125, 0.3662423372914977], "isController": false}, {"data": ["知识库版本", 671, 0, 0.0, 375.44709388971665, 2, 5477, 108.0, 788.6000000000012, 1522.7999999999984, 4703.479999999999, 1.1197871903688288, 0.21652135126272276, 0.275572628879829], "isController": false}, {"data": ["评估分布", 785, 0, 0.0, 624.464968152867, 5, 12665, 195.0, 1793.0, 2709.0, 5400.98, 1.2850314300680983, 0.8721648866184848, 0.3325520790703575], "isController": false}, {"data": ["配置版本", 762, 0, 0.0, 982.3871391076117, 7, 19523, 354.0, 2448.9000000000024, 4078.950000000002, 9534.220000000001, 1.2602873852179206, 0.34460983189552513, 0.31384109690485323], "isController": false}, {"data": ["批量刷新状态", 593, 0, 0.0, 596.6441821247889, 2, 14738, 208.0, 1642.2000000000003, 2486.0999999999995, 4998.339999999891, 0.9932831945863553, 0.38315123228672887, 0.25317081424515503], "isController": false}, {"data": ["日志", 723, 0, 0.0, 1492.3941908713703, 81, 22526, 599.0, 3423.6000000000013, 5465.0, 19109.35999999998, 1.1882535466820936, 50.58169584674159, 0.28429894427452435], "isController": false}, {"data": ["向量库状态", 683, 14, 2.049780380673499, 5103.374816983895, 537, 30013, 3162.0, 12434.6, 14382.199999999999, 30012.16, 1.127823894344533, 0.46974870157829296, 0.2804917530973875], "isController": false}, {"data": ["评估列表", 789, 0, 0.0, 661.0621039290239, 6, 15158, 198.0, 1755.0, 2672.5, 6618.100000000011, 1.3031629366586837, 0.2557966311214799, 0.3207002539433479], "isController": false}, {"data": ["配置备份", 766, 0, 0.0, 1097.2610966057437, 7, 20941, 386.0, 2818.500000000002, 4365.6, 13726.54, 1.2645188555278954, 1.9782804751520393, 0.3148948321871224], "isController": false}, {"data": ["近期反馈", 538, 1, 0.18587360594795538, 707.271375464684, 3, 30015, 175.0, 1627.0000000000002, 3719.599999999995, 8832.430000000028, 0.8937144299995681, 0.1706082989192368, 0.22998247871198807], "isController": false}, {"data": ["商品摘要", 798, 0, 0.0, 801.7531328320804, 5, 12894, 238.0, 2458.0, 3218.8499999999995, 9679.02, 1.3061946033538756, 0.30486377949372684, 0.34185561884652216], "isController": false}, {"data": ["隧道状态", 671, 0, 0.0, 3652.0715350223554, 133, 21678, 2381.0, 8648.800000000028, 12106.4, 21603.12, 1.1098577198791895, 0.30022518399075726, 0.2752967391106583], "isController": false}, {"data": ["通知列表", 742, 1, 0.1347708894878706, 996.3733153638816, 5, 30011, 336.0, 2676.400000000001, 4047.1000000000004, 9728.360000000182, 1.2302978249262984, 0.2897743488499534, 0.3047602484057529], "isController": false}, {"data": ["Prompt列表", 755, 1, 0.13245033112582782, 908.854304635761, 4, 30004, 287.0, 2696.9999999999995, 3803.999999999999, 6785.959999999998, 1.237694772993664, 7.858668614908894, 0.29935717740018525], "isController": false}, {"data": ["批量刷新历史", 590, 0, 0.0, 1541.6762711864405, 9, 21707, 568.5, 3948.099999999999, 5798.499999999993, 13778.370000000254, 0.9798092859349208, 11.332872248645703, 0.2506933915185051], "isController": false}, {"data": ["砍价评估", 831, 0, 0.0, 668.3429602888091, 5, 14744, 203.0, 1708.6000000000008, 3054.9999999999986, 6136.799999999988, 1.3673790420777578, 0.6129169729625888, 0.39525800435060193], "isController": false}, {"data": ["反爬频率统计", 698, 0, 0.0, 621.2765042979944, 3, 14485, 198.0, 1656.4000000000003, 2793.8999999999983, 5672.9699999999975, 1.1631104038392641, 0.33848330111728586, 0.29645685097856245], "isController": false}, {"data": ["DB表列表", 563, 0, 0.0, 1060.7939609236241, 5, 9508, 446.0, 3177.6000000000013, 4874.8, 6803.240000000001, 0.9417219628630354, 0.46902168072280087, 0.23543049071575886], "isController": false}, {"data": ["价格分类统计", 866, 3, 0.3464203233256351, 1495.088914549655, 10, 30012, 547.5, 3246.800000000002, 6695.449999999996, 15787.410000000233, 1.414843109256603, 1.6853785011648765, 0.3607468290604854], "isController": false}, {"data": ["知识库状态", 672, 1, 0.1488095238095238, 510.9404761904762, 2, 30003, 134.5, 1261.1000000000015, 2193.0000000000023, 4533.0, 1.1216282303143397, 0.22079415232362312, 0.2734275245815175], "isController": false}, {"data": ["卖家价格趋势", 875, 0, 0.0, 749.6262857142857, 4, 34568, 192.0, 1711.999999999999, 3775.999999999998, 10605.840000000006, 1.4303602546204723, 2.06173021076154, 0.4036856577981606], "isController": false}, {"data": ["阈值建议", 775, 0, 0.0, 708.5225806451614, 4, 20652, 217.0, 2005.3999999999987, 2804.5999999999963, 6439.200000000001, 1.278620475745807, 0.4607528862794949, 0.3408822166783255], "isController": false}, {"data": ["未读计数", 740, 0, 0.0, 959.5499999999998, 3, 13098, 318.5, 2850.0, 3869.649999999997, 6820.630000000017, 1.2246039481893238, 0.21645831506080818, 0.31930591227202093], "isController": false}, {"data": ["DB表行", 552, 0, 0.0, 838.5380434782608, 5, 20605, 379.5, 2059.7, 3549.1000000000004, 6796.210000000047, 0.9168917370115309, 3.441925622140942, 0.2471309759913892], "isController": false}, {"data": ["配置", 770, 3, 0.38961038961038963, 1049.0831168831173, 3, 30013, 341.0, 2761.0999999999995, 4031.799999999989, 11317.669999999998, 1.2697910121883447, 8.76395108150739, 0.3050941526330024], "isController": false}, {"data": ["错误日志详情", 724, 0, 0.0, 795.2665745856351, 5, 16252, 289.5, 2190.5, 3407.75, 6470.0, 1.2101943832939686, 41.17733662375826, 0.2990031044661856], "isController": false}, {"data": ["反馈统计", 779, 1, 0.12836970474967907, 874.175866495507, 5, 30016, 242.0, 2550.0, 3910.0, 7147.400000000027, 1.2753765553372627, 0.34498333384495744, 0.3321175865667977], "isController": false}, {"data": ["DB表结构", 555, 0, 0.0, 1626.7243243243252, 4, 20351, 352.0, 5529.8, 6931.799999999935, 14891.279999999999, 0.9224065003897375, 3.547301561069127, 0.24231186387191347], "isController": false}, {"data": ["订单列表", 806, 1, 0.12406947890818859, 824.6166253101741, 4, 30013, 208.5, 1892.900000000001, 3268.499999999999, 9438.989999999947, 1.3289409033500523, 0.2647209626000415, 0.331823023324067], "isController": false}, {"data": ["日志搜索", 721, 1, 0.13869625520110956, 2153.868238557559, 81, 30001, 984.0, 5458.6, 7033.8, 15355.499999999985, 1.1975848981388435, 144.48093483720072, 0.2943093954770823], "isController": false}, {"data": ["反爬策略", 709, 2, 0.2820874471086037, 4833.180535966149, 2471, 30011, 3688.0, 8310.0, 12603.5, 18154.499999999993, 1.1616571227276824, 0.4834403186364865, 0.2929887505427347], "isController": false}, {"data": ["参数计算器规则", 569, 0, 0.0, 598.8523725834798, 3, 12629, 213.0, 1496.0, 2247.0, 5750.3999999999805, 0.9516944007252279, 3.37182352131946, 0.2444293236237646], "isController": false}, {"data": ["Cron示例", 573, 3, 0.5235602094240838, 2134.41012216405, 3, 30013, 356.0, 5676.4000000000015, 10763.299999999981, 20107.26, 0.9617676382813732, 0.6854925277326454, 0.23731443381595158], "isController": false}, {"data": ["Dashboard统计", 894, 0, 0.0, 425.41275167785307, 3, 12838, 108.0, 1003.5, 2069.0, 4876.899999999994, 1.4700223956432088, 0.6145069238219267, 0.353149911453349], "isController": false}, {"data": ["今日统计", 888, 0, 0.0, 447.7060810810811, 1, 19479, 73.5, 762.8000000000006, 2023.7999999999993, 7480.22, 1.450549019735961, 0.5382896752926417, 0.3569710478256466], "isController": false}, {"data": ["错误日志", 729, 3, 0.411522633744856, 2092.9286694101493, 38, 30015, 930.0, 5161.0, 6907.5, 14839.300000000001, 1.2079836284248986, 3168.8577239129804, 0.2948790411112124], "isController": false}, {"data": ["菜单", 756, 0, 0.0, 757.3121693121686, 3, 17098, 161.5, 1860.1000000000017, 3578.899999999996, 11421.439999999975, 1.2609814639060735, 4.817343248828672, 0.30169966665721487], "isController": false}, {"data": ["价格分类对比", 852, 1, 0.11737089201877934, 1095.5481220657282, 10, 30014, 495.0, 2534.400000000001, 4208.699999999962, 11073.950000000013, 1.392059054674263, 1.8657447526154207, 0.3625425036517042], "isController": false}, {"data": ["评估漏斗", 879, 0, 0.0, 746.9442548350394, 2, 14767, 143.0, 2299.0, 4334.0, 8917.600000000013, 1.4747901486031438, 1.1536200283507012, 0.3715779866597764], "isController": false}, {"data": ["售出区间", 837, 3, 0.35842293906810035, 1393.2174432497022, 10, 30010, 562.0, 3252.200000000003, 5767.599999999997, 12227.62, 1.3772155564477382, 0.6799163032005041, 0.34575005800101355], "isController": false}, {"data": ["关于", 749, 0, 0.0, 402.3591455273699, 2, 13481, 85.0, 929.0, 1927.5, 5053.0, 1.238464832724573, 0.3640409322754849, 0.2975218250490674], "isController": false}, {"data": ["任务预检", 817, 0, 0.0, 712.3439412484703, 3, 11283, 209.0, 2128.800000000001, 2929.499999999994, 6464.839999999974, 1.3352989631411722, 0.39120086810776533, 0.34556076682852604], "isController": false}, {"data": ["模板", 752, 0, 0.0, 826.9188829787234, 14, 14582, 240.5, 2329.0000000000005, 3544.7, 11133.0, 1.2325141157284865, 3.5723651323067847, 0.300906766535275], "isController": false}, {"data": ["业务KPI", 883, 0, 0.0, 472.18799546998804, 1, 19460, 72.0, 878.4000000000007, 2525.799999999992, 7497.16, 1.453710914026911, 1.4494519953334728, 0.367686647200166], "isController": false}, {"data": ["自动采集统计", 782, 0, 0.0, 753.9194373401532, 4, 14121, 240.0, 1933.9000000000012, 3125.299999999991, 7334.949999999901, 1.2801477244637538, 0.3737931343893188, 0.338789095048513], "isController": false}, {"data": ["配置原始", 769, 0, 0.0, 761.6111833550065, 55, 10600, 364.0, 2121.0, 2864.0, 5163.299999999984, 1.2592231133759295, 9.511807404260564, 0.30865722798570155], "isController": false}, {"data": ["会话列表", 547, 0, 0.0, 923.9524680073131, 4, 19602, 233.0, 2443.5999999999995, 4795.800000000001, 12575.319999999956, 0.9085578844387454, 0.8970234581714567, 0.22802673466870857], "isController": false}, {"data": ["价格直方图", 873, 0, 0.0, 696.7651775486826, 2, 34572, 147.0, 1708.8000000000006, 2740.999999999999, 10451.04, 1.4265032206619106, 1.1952536751249212, 0.3580188747169053], "isController": false}, {"data": ["最新评估", 789, 0, 0.0, 725.5982256020274, 4, 9676, 215.0, 2229.0, 3367.0, 6537.400000000004, 1.2915328481491304, 0.26864892251539524, 0.34432467533663336], "isController": false}, {"data": ["商品批量", 798, 795, 99.62406015037594, 104.3571428571428, 16, 1851, 68.0, 204.10000000000002, 288.2999999999997, 574.4699999999996, 1.319418265510605, 3.1665621791358305, 0.0013078702555504851], "isController": false}, {"data": ["反爬健康", 684, 0, 0.0, 467.57456140350905, 2, 12632, 101.5, 1329.5, 2162.0, 6264.15, 1.1392348139499637, 0.3704738213333378, 0.2859212374854889], "isController": false}]}, function(index, item){
        switch(index){
            // Errors pct
            case 3:
                item = item.toFixed(2) + '%';
                break;
            // Mean
            case 4:
            // Mean
            case 7:
            // Median
            case 8:
            // Percentile 1
            case 9:
            // Percentile 2
            case 10:
            // Percentile 3
            case 11:
            // Throughput
            case 12:
            // Kbytes/s
            case 13:
            // Sent Kbytes/s
                item = item.toFixed(2);
                break;
        }
        return item;
    }, [[0, 0]], 0, summaryTableHeader);

    // Create error table
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["Non HTTP response code: java.net.SocketException/Non HTTP response message: Connection reset", 795, 33.13880783659858, 1.6203986792222087], "isController": false}, {"data": ["500/Internal Server Error", 804, 33.51396415172989, 1.6387428152134034], "isController": false}, {"data": ["404/Not Found", 756, 31.513130471029594, 1.5409074232603643], "isController": false}, {"data": ["Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 44, 1.8340975406419342, 0.08968244262361909], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 49062, 2399, "500/Internal Server Error", 804, "Non HTTP response code: java.net.SocketException/Non HTTP response message: Connection reset", 795, "404/Not Found", 756, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 44, "", ""], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["偏好", 756, 756, "404/Not Found", 756, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["账号统计", 713, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["任务详情", 824, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["维护状态", 647, 3, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 3, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["订单详情", 804, 804, "500/Internal Server Error", 804, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["向量库状态", 683, 14, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 14, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["近期反馈", 538, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["通知列表", 742, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["Prompt列表", 755, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["价格分类统计", 866, 3, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 3, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["知识库状态", 672, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["配置", 770, 3, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 3, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["反馈统计", 779, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["订单列表", 806, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["日志搜索", 721, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["反爬策略", 709, 2, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 2, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["Cron示例", 573, 3, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 3, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["错误日志", 729, 3, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 3, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["价格分类对比", 852, 1, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 1, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["售出区间", 837, 3, "Non HTTP response code: java.net.SocketTimeoutException/Non HTTP response message: Read timed out", 3, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["商品批量", 798, 795, "Non HTTP response code: java.net.SocketException/Non HTTP response message: Connection reset", 795, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
