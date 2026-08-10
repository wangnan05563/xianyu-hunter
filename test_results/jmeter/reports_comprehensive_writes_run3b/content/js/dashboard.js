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

    var data = {"OkPercent": 57.13985499632237, "KoPercent": 42.86014500367763};
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
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.5637280655668803, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.9882525697503671, 500, 1500, "创建会话"], "isController": false}, {"data": [0.9815770081061165, 500, 1500, "清理缓存(dry_run)"], "isController": false}, {"data": [0.0, 500, 1500, "删除会话"], "isController": false}, {"data": [0.9948717948717949, 500, 1500, "通知全部已读"], "isController": false}, {"data": [0.0, 500, 1500, "提交评估反馈"], "isController": false}, {"data": [0.981536189069424, 500, 1500, "配置预览"], "isController": false}, {"data": [0.0, 500, 1500, "偏好UPSERT"], "isController": false}]}, function(index, item){
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
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 9517, 4079, 42.86014500367763, 242.02721445833842, 6, 764, 236.0, 375.0, 424.0, 524.0, 79.38043723048435, 23.7970225298396, 23.397677043627127], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["创建会话", 1362, 0, 0.0, 269.9508076358292, 8, 650, 259.0, 388.0, 450.6999999999998, 545.8499999999995, 11.369707492987846, 5.06307286797115, 3.319865762112662], "isController": false}, {"data": ["清理缓存(dry_run)", 1357, 0, 0.0, 315.90935887988246, 10, 764, 309.0, 434.20000000000005, 489.0, 586.4200000000001, 11.329292524503666, 2.611047886506704, 3.4408300538287495], "isController": false}, {"data": ["删除会话", 1360, 1360, 100.0, 209.8963235294117, 7, 559, 204.0, 307.0, 362.9000000000001, 458.1700000000003, 11.360314079271603, 2.695855782483398, 3.4613456960280664], "isController": false}, {"data": ["通知全部已读", 1365, 0, 0.0, 240.7575091575091, 7, 611, 235.0, 344.8000000000002, 402.70000000000005, 502.0, 11.398842579061203, 2.1372829835739755, 3.150266064330391], "isController": false}, {"data": ["提交评估反馈", 1352, 1352, 100.0, 216.91568047337262, 7, 574, 205.0, 325.70000000000005, 364.6999999999998, 458.0500000000004, 11.295564485809528, 2.581212978202568, 3.4526481289632645], "isController": false}, {"data": ["配置预览", 1354, 0, 0.0, 305.1824224519944, 44, 626, 298.0, 421.5, 476.25, 571.0, 11.30556761631208, 6.193772883545974, 3.3342591993420396], "isController": false}, {"data": ["偏好UPSERT", 1367, 1367, 100.0, 136.37966349670825, 6, 511, 128.0, 209.20000000000005, 249.0, 355.6399999999999, 11.410113016042603, 2.540532976228236, 3.2648077282231274], "isController": false}]}, function(index, item){
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
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["405/Method Not Allowed", 1367, 33.513115959794064, 14.363770095618367], "isController": false}, {"data": ["404/Not Found", 2712, 66.48688404020594, 28.496374908059263], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 9517, 4079, "404/Not Found", 2712, "405/Method Not Allowed", 1367, "", "", "", "", "", ""], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": [], "isController": false}, {"data": [], "isController": false}, {"data": ["删除会话", 1360, 1360, "404/Not Found", 1360, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["提交评估反馈", 1352, 1352, "404/Not Found", 1352, "", "", "", "", "", "", "", ""], "isController": false}, {"data": [], "isController": false}, {"data": ["偏好UPSERT", 1367, 1367, "405/Method Not Allowed", 1367, "", "", "", "", "", "", "", ""], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
