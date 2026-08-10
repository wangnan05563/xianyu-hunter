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

    var data = {"OkPercent": 94.80506978982834, "KoPercent": 5.194930210171667};
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
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.3998395636130274, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.3450363196125908, 500, 1500, "账号"], "isController": false}, {"data": [0.44986072423398327, 500, 1500, "反爬指纹"], "isController": false}, {"data": [0.3916083916083916, 500, 1500, "任务运行记录"], "isController": false}, {"data": [0.28687196110210694, 500, 1500, "价格趋势"], "isController": false}, {"data": [0.0, 500, 1500, "偏好"], "isController": false}, {"data": [0.8093699515347335, 500, 1500, "趋势"], "isController": false}, {"data": [0.3702770780856423, 500, 1500, "账号统计"], "isController": false}, {"data": [0.48390342052313884, 500, 1500, "配置导出"], "isController": false}, {"data": [0.43804537521815007, 500, 1500, "任务详情"], "isController": false}, {"data": [0.0, 500, 1500, "维护状态"], "isController": false}, {"data": [0.43685121107266434, 500, 1500, "任务列表"], "isController": false}, {"data": [0.5425925925925926, 500, 1500, "客服配置"], "isController": false}, {"data": [0.0, 500, 1500, "订单详情"], "isController": false}, {"data": [0.0836734693877551, 500, 1500, "检查更新"], "isController": false}, {"data": [0.39818548387096775, 500, 1500, "配置分享"], "isController": false}, {"data": [0.390715667311412, 500, 1500, "评估卖家价格趋势"], "isController": false}, {"data": [0.6379821958456974, 500, 1500, "知识库版本"], "isController": false}, {"data": [0.375, 500, 1500, "评估分布"], "isController": false}, {"data": [0.3963782696177062, 500, 1500, "配置版本"], "isController": false}, {"data": [0.49348534201954397, 500, 1500, "批量刷新状态"], "isController": false}, {"data": [0.3137472283813747, 500, 1500, "日志"], "isController": false}, {"data": [0.12536023054755044, 500, 1500, "向量库状态"], "isController": false}, {"data": [0.4007220216606498, 500, 1500, "评估列表"], "isController": false}, {"data": [0.36773547094188375, 500, 1500, "配置备份"], "isController": false}, {"data": [0.5518518518518518, 500, 1500, "近期反馈"], "isController": false}, {"data": [0.4269162210338681, 500, 1500, "商品摘要"], "isController": false}, {"data": [0.1884272997032641, 500, 1500, "隧道状态"], "isController": false}, {"data": [0.33161157024793386, 500, 1500, "通知列表"], "isController": false}, {"data": [0.40408163265306124, 500, 1500, "Prompt列表"], "isController": false}, {"data": [0.313953488372093, 500, 1500, "批量刷新历史"], "isController": false}, {"data": [0.42055267702936094, 500, 1500, "砍价评估"], "isController": false}, {"data": [0.45148247978436656, 500, 1500, "反爬频率统计"], "isController": false}, {"data": [0.3975694444444444, 500, 1500, "DB表列表"], "isController": false}, {"data": [0.2586490939044481, 500, 1500, "价格分类统计"], "isController": false}, {"data": [0.6774193548387096, 500, 1500, "知识库状态"], "isController": false}, {"data": [0.5310457516339869, 500, 1500, "卖家价格趋势"], "isController": false}, {"data": [0.3934740882917466, 500, 1500, "阈值建议"], "isController": false}, {"data": [0.31921487603305787, 500, 1500, "未读计数"], "isController": false}, {"data": [0.3368421052631579, 500, 1500, "DB表行"], "isController": false}, {"data": [0.39665354330708663, 500, 1500, "配置"], "isController": false}, {"data": [0.3468085106382979, 500, 1500, "错误日志详情"], "isController": false}, {"data": [0.3797709923664122, 500, 1500, "反馈统计"], "isController": false}, {"data": [0.3989547038327526, 500, 1500, "DB表结构"], "isController": false}, {"data": [0.4192982456140351, 500, 1500, "订单列表"], "isController": false}, {"data": [0.11948955916473318, 500, 1500, "日志搜索"], "isController": false}, {"data": [0.0, 500, 1500, "反爬策略"], "isController": false}, {"data": [0.4846938775510204, 500, 1500, "参数计算器规则"], "isController": false}, {"data": [0.4280936454849498, 500, 1500, "Cron示例"], "isController": false}, {"data": [0.7174603174603175, 500, 1500, "Dashboard统计"], "isController": false}, {"data": [0.8006379585326954, 500, 1500, "今日统计"], "isController": false}, {"data": [0.21694214876033058, 500, 1500, "错误日志"], "isController": false}, {"data": [0.43584521384928715, 500, 1500, "菜单"], "isController": false}, {"data": [0.23395270270270271, 500, 1500, "价格分类对比"], "isController": false}, {"data": [0.5575364667747164, 500, 1500, "评估漏斗"], "isController": false}, {"data": [0.30631399317406144, 500, 1500, "售出区间"], "isController": false}, {"data": [0.5989795918367347, 500, 1500, "关于"], "isController": false}, {"data": [0.43859649122807015, 500, 1500, "任务预检"], "isController": false}, {"data": [0.46938775510204084, 500, 1500, "模板"], "isController": false}, {"data": [0.8134087237479806, 500, 1500, "业务KPI"], "isController": false}, {"data": [0.4032258064516129, 500, 1500, "自动采集统计"], "isController": false}, {"data": [0.39741035856573703, 500, 1500, "配置原始"], "isController": false}, {"data": [0.5756457564575646, 500, 1500, "会话列表"], "isController": false}, {"data": [0.5977011494252874, 500, 1500, "价格直方图"], "isController": false}, {"data": [0.39686924493554326, 500, 1500, "最新评估"], "isController": false}, {"data": [0.0, 500, 1500, "商品批量"], "isController": false}, {"data": [0.6494252873563219, 500, 1500, "反爬健康"], "isController": false}]}, function(index, item){
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
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 31165, 1619, 5.194930210171667, 1909.964286860259, 0, 22511, 1990.5, 5389.9000000000015, 6565.950000000001, 8842.990000000002, 51.131152678130505, 2310.5779129447624, 12.734125953018076], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["账号", 413, 0, 0.0, 2801.549636803873, 6, 8360, 2199.0, 6662.6, 7143.799999999999, 8325.44, 0.6825837032727657, 0.1293176156590982, 0.16597982628410027], "isController": false}, {"data": ["反爬指纹", 359, 0, 0.0, 2093.2674094707518, 3, 7488, 1171.0, 5616.0, 7005.0, 7484.0, 0.5959594282773619, 0.16237566454041402, 0.15248180684440313], "isController": false}, {"data": ["任务运行记录", 572, 0, 0.0, 1647.4510489510494, 7, 8725, 1308.0, 3632.7, 4164.200000000001, 6121.019999999998, 0.9416071851871362, 0.24275810243105855, 0.2399994876307056], "isController": false}, {"data": ["价格趋势", 617, 0, 0.0, 1959.5170178282021, 10, 12887, 1724.0, 3431.800000000004, 4666.8, 9002.620000000023, 1.0154105418375474, 0.41350214447876693, 0.2558358591739133], "isController": false}, {"data": ["偏好", 490, 490, 100.0, 905.3673469387761, 2, 5054, 611.5, 2183.0, 3302.75, 4302.89999999998, 0.831729283999905, 0.16082265452341912, 0.2046833784843516], "isController": false}, {"data": ["趋势", 619, 0, 0.0, 594.3828756058157, 2, 6893, 308.0, 1411.0, 2788.0, 4695.799999999998, 1.0450026420502985, 1.7144574596137712, 0.25716861894206566], "isController": false}, {"data": ["账号统计", 397, 0, 0.0, 2467.5113350125944, 6, 8613, 1536.0, 6338.199999999998, 7268.7, 8438.179999999998, 0.6561408669984283, 0.13904547669790912, 0.16339445418417892], "isController": false}, {"data": ["配置导出", 497, 0, 0.0, 1282.6177062374238, 25, 4644, 940.0, 2905.0, 3585.7999999999997, 4507.279999999998, 0.8591332607305225, 8.932804518552611, 0.21310532053276635], "isController": false}, {"data": ["任务详情", 573, 0, 0.0, 1468.4764397905751, 4, 8474, 1041.0, 3325.2, 4135.0, 6861.439999999999, 0.9432952777617727, 0.6844417884540986, 0.23582381944044314], "isController": false}, {"data": ["维护状态", 327, 0, 0.0, 10266.685015290512, 3227, 22511, 9558.0, 16974.999999999993, 17971.39999999999, 21665.319999999985, 0.5435234280205442, 0.22765627337400063, 0.137473210798165], "isController": false}, {"data": ["任务列表", 578, 0, 0.0, 1489.3512110726645, 7, 8133, 1111.5, 3386.6000000000013, 4470.25, 5834.140000000001, 0.951340105733717, 0.7590281898285614, 0.2452673710094739], "isController": false}, {"data": ["客服配置", 270, 0, 0.0, 1372.2703703703696, 6, 7006, 770.0, 3508.0, 4909.15, 6508.500000000014, 0.46862552134589247, 0.7482448509770842, 0.11669873822578378], "isController": false}, {"data": ["订单详情", 568, 568, 100.0, 1924.406690140845, 34, 7083, 1437.5, 4378.300000000001, 5073.4, 6097.3099999999995, 0.935185703513203, 0.26576078097884964, 0.24749543520710743], "isController": false}, {"data": ["检查更新", 490, 0, 0.0, 3808.9755102040804, 641, 11815, 3789.0, 6332.0, 6965.7, 9676.759999999987, 0.8093875744141025, 0.2798078138111253, 0.20471814626294196], "isController": false}, {"data": ["配置分享", 496, 0, 0.0, 1866.9959677419365, 29, 6474, 1440.5, 4253.5, 4571.05, 5005.229999999999, 0.8486945332778943, 7.562000900026864, 0.209687223554011], "isController": false}, {"data": ["评估卖家价格趋势", 517, 0, 0.0, 1905.0212765957458, 4, 8218, 1353.0, 4333.4, 5019.099999999999, 5882.120000000001, 0.8614312088029271, 0.2229289749343513, 0.24816621737974953], "isController": false}, {"data": ["知识库版本", 337, 0, 0.0, 1062.53115727003, 4, 5445, 482.0, 3162.3999999999996, 4381.699999999979, 5444.0, 0.565796034726781, 0.10940196765224866, 0.13923886792104376], "isController": false}, {"data": ["评估分布", 532, 0, 0.0, 1895.4567669172925, 5, 7014, 1517.5, 4113.0, 4583.4, 6173.999999999987, 0.8772508409735505, 0.5953997406998218, 0.22702292271288171], "isController": false}, {"data": ["配置版本", 497, 0, 0.0, 1784.6096579476866, 11, 6424, 1279.0, 4078.2, 4755.399999999999, 6321.319999999999, 0.8629910540645663, 0.23597411634577986, 0.21490499881490666], "isController": false}, {"data": ["批量刷新状态", 307, 0, 0.0, 1944.104234527687, 4, 7602, 946.0, 5077.8, 5744.39999999998, 7538.000000000006, 0.516395124691761, 0.19919538501293513, 0.13162024174272421], "isController": false}, {"data": ["日志", 451, 0, 0.0, 2874.117516629713, 88, 8709, 1976.0, 6737.0, 7882.5999999999985, 8494.840000000002, 0.744538947145989, 31.71184165670646, 0.17813675981520247], "isController": false}, {"data": ["向量库状态", 347, 0, 0.0, 2731.939481268011, 606, 6680, 2520.0, 4982.4, 5385.399999999993, 6677.52, 0.5770964233326571, 0.214720446572014, 0.14652838873680746], "isController": false}, {"data": ["评估列表", 554, 0, 0.0, 1791.3447653429612, 6, 7574, 1356.5, 4179.0, 4992.75, 5894.450000000001, 0.9121819094898203, 0.17905133184321667, 0.22448226678851044], "isController": false}, {"data": ["配置备份", 499, 0, 0.0, 1823.0080160320645, 12, 6998, 1473.0, 3593.0, 4688.0, 6098.0, 0.8726858086247241, 1.3652760404461015, 0.21731921992119593], "isController": false}, {"data": ["近期反馈", 270, 0, 0.0, 1411.855555555555, 6, 7688, 641.0, 3478.2, 4608.849999999998, 7645.570000000001, 0.46269559599476984, 0.0863035730810557, 0.11928870834240159], "isController": false}, {"data": ["商品摘要", 561, 0, 0.0, 1701.486631016042, 6, 7910, 1322.0, 3944.4, 4545.9, 6220.239999999996, 0.9326559247757303, 0.21768043556777297, 0.24409354281239815], "isController": false}, {"data": ["隧道状态", 337, 0, 0.0, 2670.9999999999986, 423, 11665, 2008.0, 5535.0, 6552.1, 9953.90000000002, 0.5602650702160097, 0.15155607856429168, 0.13897199983873676], "isController": false}, {"data": ["通知列表", 484, 0, 0.0, 2759.7190082644615, 6, 8663, 2171.0, 6377.5, 6889.75, 8430.15, 0.8194431511313903, 0.1904565136418661, 0.20326031287829407], "isController": false}, {"data": ["Prompt列表", 490, 0, 0.0, 1937.1142857142859, 5, 7598, 1398.0, 4782.8, 5232.7, 6369.4499999999825, 0.8282483392775647, 5.263097601249133, 0.20059139466878517], "isController": false}, {"data": ["批量刷新历史", 301, 0, 0.0, 2450.229235880399, 13, 8716, 1400.0, 5755.0, 7168.5999999999985, 8379.380000000001, 0.5070575333419808, 5.845348926335153, 0.12973542356992088], "isController": false}, {"data": ["砍价评估", 579, 0, 0.0, 1584.2573402417952, 6, 8336, 1232.0, 3266.0, 3917.0, 7545.4, 0.9552768735553293, 0.42819539547060176, 0.2761347212620874], "isController": false}, {"data": ["反爬频率统计", 371, 0, 0.0, 2107.059299191375, 4, 7472, 1224.0, 5269.0, 6338.199999999997, 7467.5599999999995, 0.6162391472977664, 0.17933522060032656, 0.15706876703585648], "isController": false}, {"data": ["DB表列表", 288, 0, 0.0, 2122.881944444444, 8, 8599, 1104.5, 5447.500000000001, 6330.4, 8497.810000000001, 0.48628523668414253, 0.24219284248917256, 0.12157130917103563], "isController": false}, {"data": ["价格分类统计", 607, 0, 0.0, 2046.3723228995063, 9, 11804, 1928.0, 3604.6000000000013, 4492.200000000006, 8121.1999999999625, 0.9987840174811885, 1.1850806457418397, 0.25554825447272594], "isController": false}, {"data": ["知识库状态", 341, 0, 0.0, 840.4838709677415, 9, 5465, 451.0, 2740.4000000000015, 3322.3999999999996, 4388.48, 0.5676483709657014, 0.10976013422969616, 0.13858602806779818], "isController": false}, {"data": ["卖家价格趋势", 612, 0, 0.0, 1250.101307189543, 5, 8647, 858.5, 2471.200000000001, 3972.9500000000007, 6972.710000000001, 1.0085795179253585, 1.4537728207595988, 0.28464793035198105], "isController": false}, {"data": ["阈值建议", 521, 0, 0.0, 1944.8502879078685, 5, 7316, 1462.0, 4273.4, 5428.499999999999, 7033.24, 0.8581768107777783, 0.3092453546650393, 0.22879127865462254], "isController": false}, {"data": ["未读计数", 484, 0, 0.0, 2824.57438016529, 5, 8634, 2053.5, 6478.0, 8072.5, 8584.2, 0.8082751341836921, 0.14286894461645339, 0.2107514265889119], "isController": false}, {"data": ["DB表行", 285, 0, 0.0, 2350.1087719298257, 9, 11916, 1443.0, 5803.400000000002, 7196.099999999999, 7577.079999999993, 0.4815197777912941, 1.8075801033493504, 0.12978462760780976], "isController": false}, {"data": ["配置", 508, 0, 0.0, 2015.8543307086613, 4, 7061, 1329.0, 4583.4, 5424.699999999999, 6035.889999999994, 0.8366119849607467, 5.788472571725479, 0.20179996121611762], "isController": false}, {"data": ["错误日志详情", 470, 0, 0.0, 2725.531914893618, 7, 9150, 1972.0, 6625.8, 7129.699999999999, 8514.300000000003, 0.7758899622950495, 26.399959049105583, 0.1916993754498511], "isController": false}, {"data": ["反馈统计", 524, 0, 0.0, 1980.154580152672, 5, 8452, 1440.0, 4461.5, 5218.5, 7771.25, 0.873624541513838, 0.23376281677225744, 0.22779077400800268], "isController": false}, {"data": ["DB表结构", 287, 0, 0.0, 2438.815331010452, 5, 11688, 1097.0, 6830.999999999996, 7510.199999999984, 10120.080000000005, 0.48493409458411413, 1.8649125629611734, 0.12738991351867843], "isController": false}, {"data": ["订单列表", 570, 0, 0.0, 1687.7403508771924, 3, 8655, 1243.0, 4200.9, 4876.899999999991, 7052.019999999999, 0.9383194862618504, 0.18418185228382022, 0.2345798715654626], "isController": false}, {"data": ["日志搜索", 431, 0, 0.0, 4101.129930394431, 123, 12770, 4079.0, 8214.2, 8835.0, 10437.04, 0.711126070607724, 88.92548177863189, 0.17500368143861958], "isController": false}, {"data": ["反爬策略", 387, 0, 0.0, 4793.258397932818, 2478, 12777, 4323.0, 7881.799999999999, 8879.399999999998, 10851.080000000005, 0.6379842993217913, 0.2616732477687035, 0.16136516945736717], "isController": false}, {"data": ["参数计算器规则", 294, 0, 0.0, 1502.5850340136058, 4, 7606, 786.5, 4101.5, 4913.0, 6167.750000000002, 0.49545078437948165, 1.7553666462194915, 0.1272495666912145], "isController": false}, {"data": ["Cron示例", 299, 0, 0.0, 1957.1772575250832, 4, 7498, 1429.0, 5223.0, 6052.0, 6922.0, 0.5042677239985901, 0.3545632434365087, 0.12508203310121277], "isController": false}, {"data": ["Dashboard统计", 630, 0, 0.0, 740.9444444444448, 4, 6388, 395.0, 1797.1, 3074.7499999999977, 5196.939999999999, 1.039537059496171, 0.43449400533629023, 0.24973253577740048], "isController": false}, {"data": ["今日统计", 627, 0, 0.0, 616.6347687400322, 2, 6878, 303.0, 1587.800000000001, 2862.6000000000004, 5952.56, 1.0319017274067832, 0.382932281654861, 0.2539445657290131], "isController": false}, {"data": ["错误日志", 484, 0, 0.0, 3343.3657024793383, 46, 10299, 2600.0, 7108.5, 8241.0, 9227.499999999995, 0.7988288245167828, 2104.1946043569183, 0.19580667475948488], "isController": false}, {"data": ["菜单", 491, 0, 0.0, 1860.079429735235, 3, 6480, 1277.0, 4546.8, 4919.4, 6040.919999999998, 0.834252256813768, 3.187104324858848, 0.19960137003845035], "isController": false}, {"data": ["价格分类对比", 592, 0, 0.0, 2120.277027027026, 11, 8784, 1949.0, 3526.7, 5082.25, 7752.960000000032, 0.9756306578750039, 1.3062398749478812, 0.2543880719263926], "isController": false}, {"data": ["评估漏斗", 617, 0, 0.0, 1189.3760129659645, 3, 8537, 789.0, 2390.4000000000015, 4680.600000000002, 7070.320000000006, 1.0274925019692218, 0.8037319278099089, 0.2588799467852141], "isController": false}, {"data": ["售出区间", 586, 0, 0.0, 1899.8259385665538, 15, 9325, 1692.5, 3582.4000000000005, 4601.049999999999, 8344.189999999999, 0.9645788855986397, 0.46910184084777595, 0.24302866453559477], "isController": false}, {"data": ["关于", 490, 0, 0.0, 916.0285714285711, 2, 5209, 656.5, 2192.2000000000007, 2998.2499999999986, 3851.6899999999964, 0.818623176057444, 0.24063044530594788, 0.196661427060675], "isController": false}, {"data": ["任务预检", 570, 0, 0.0, 1654.0631578947366, 3, 8647, 1176.5, 3648.8, 4651.449999999997, 6184.959999999981, 0.9427440135755137, 0.2761945352272013, 0.24397183945069448], "isController": false}, {"data": ["模板", 490, 0, 0.0, 1570.3224489795912, 14, 6863, 967.0, 3933.7000000000003, 4549.099999999999, 6786.889999999999, 0.8256386061872346, 2.3930618976208127, 0.20157192533868032], "isController": false}, {"data": ["业务KPI", 619, 0, 0.0, 548.0064620355412, 2, 6773, 312.0, 1173.0, 2193.0, 5057.999999999998, 1.0464937387890765, 1.043427839163718, 0.26468933432262776], "isController": false}, {"data": ["自动采集统计", 527, 0, 0.0, 1816.343453510437, 5, 6155, 1290.0, 4153.2, 4913.0, 5913.280000000004, 0.890788034705237, 0.2601031468524081, 0.23574566152843676], "isController": false}, {"data": ["配置原始", 502, 0, 0.0, 1734.324701195219, 42, 6304, 1290.5, 3707.8, 4642.4, 6072.979999999999, 0.888684322333947, 6.712864485598711, 0.21783180166584054], "isController": false}, {"data": ["会话列表", 271, 0, 0.0, 1324.918819188192, 7, 7829, 674.0, 3965.0000000000027, 4706.0, 6557.239999999954, 0.45798533770926214, 0.452171070726625, 0.11494358573367223], "isController": false}, {"data": ["价格直方图", 609, 0, 0.0, 1060.1510673234811, 3, 8371, 706.0, 2123.0, 3815.5, 7034.399999999993, 1.0022299204305145, 0.8397590544232241, 0.25153622026429906], "isController": false}, {"data": ["最新评估", 543, 0, 0.0, 1823.4438305709027, 4, 8434, 1334.0, 4134.200000000001, 4549.8, 5858.68, 0.9058469669140646, 0.18842324604755448, 0.24150021676517544], "isController": false}, {"data": ["商品批量", 561, 561, 100.0, 87.67379679144388, 0, 1634, 41.0, 175.8, 308.89999999999975, 949.2799999999988, 0.9447927771350043, 2.2802625252407878, 0.0], "isController": false}, {"data": ["反爬健康", 348, 0, 0.0, 897.67816091954, 2, 5015, 528.0, 2195.0, 3448.5, 4276.0, 0.5832574930989577, 0.18967260273628214, 0.14638396067034387], "isController": false}]}, function(index, item){
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
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["Non HTTP response code: org.apache.http.NoHttpResponseException/Non HTTP response message: 127.0.0.1:8011 failed to respond", 2, 0.12353304508956146, 0.006417455478902615], "isController": false}, {"data": ["Non HTTP response code: java.net.SocketException/Non HTTP response message: Software caused connection abort: recv failed", 24, 1.4823965410747375, 0.07700946574683139], "isController": false}, {"data": ["Non HTTP response code: java.net.SocketException/Non HTTP response message: Connection reset", 535, 33.04508956145769, 1.7166693406064495], "isController": false}, {"data": ["500/Internal Server Error", 568, 35.08338480543545, 1.8225573560083428], "isController": false}, {"data": ["404/Not Found", 490, 30.26559604694256, 1.5722765923311408], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 31165, 1619, "500/Internal Server Error", 568, "Non HTTP response code: java.net.SocketException/Non HTTP response message: Connection reset", 535, "404/Not Found", 490, "Non HTTP response code: java.net.SocketException/Non HTTP response message: Software caused connection abort: recv failed", 24, "Non HTTP response code: org.apache.http.NoHttpResponseException/Non HTTP response message: 127.0.0.1:8011 failed to respond", 2], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["偏好", 490, 490, "404/Not Found", 490, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["订单详情", 568, 568, "500/Internal Server Error", 568, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["商品批量", 561, 561, "Non HTTP response code: java.net.SocketException/Non HTTP response message: Connection reset", 535, "Non HTTP response code: java.net.SocketException/Non HTTP response message: Software caused connection abort: recv failed", 24, "Non HTTP response code: org.apache.http.NoHttpResponseException/Non HTTP response message: 127.0.0.1:8011 failed to respond", 2, "", "", "", ""], "isController": false}, {"data": [], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
